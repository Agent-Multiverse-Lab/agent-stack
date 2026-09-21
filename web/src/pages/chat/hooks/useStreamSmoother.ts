import { useEffect, useRef } from "react";

const START_BUFFER_MS = 180;
const RATE_SAMPLE_MS = 200;
const RATE_ADJUST_MS = 300;
const CATCH_UP_MS = 600;
const MIN_CHARS_PER_SECOND = 32;

const segmenter = new Intl.Segmenter(undefined, { granularity: "grapheme" });

export interface StreamTextChunk {
  messageId: string;
  content: string;
  threadId: string | null;
  runId: string;
  createdAt: string | null;
}

interface StreamController {
  metadata: Omit<StreamTextChunk, "content">;
  buffer: string;
  frameId: number | null;
  lastFrameAt: number;
  sampleAt: number;
  sampleChars: number;
  arrivalRate: number;
  rate: number;
  credit: number;
}

type AppendChunks = (chunks: StreamTextChunk[]) => void;

const scheduleFrame = (callback: FrameRequestCallback) =>
  typeof window.requestAnimationFrame === "function"
    ? window.requestAnimationFrame(callback)
    : window.setTimeout(() => callback(performance.now()), 16);

const cancelFrame = (frameId: number) => {
  if (typeof window.cancelAnimationFrame === "function") {
    window.cancelAnimationFrame(frameId);
  } else {
    window.clearTimeout(frameId);
  }
};

const takeFromBuffer = (value: string, count: number) => {
  if (!value || count <= 0) return { emitted: "", rest: value };
  if (count >= value.length) return { emitted: value, rest: "" };
  let end = 0;
  for (const { segment, index } of segmenter.segment(value)) {
    if (index + segment.length > count && end > 0) break;
    end = index + segment.length;
    if (end >= count) break;
  }
  return { emitted: value.slice(0, end), rest: value.slice(end) };
};

export function useStreamSmoother(appendChunks: AppendChunks) {
  const appendRef = useRef(appendChunks);
  appendRef.current = appendChunks;
  const controllersByThreadRef = useRef(
    new Map<string | null, Map<string, StreamController>>(),
  );

  function flushMessage(threadId: string | null, messageId: string) {
    const threadControllers = controllersByThreadRef.current.get(threadId);
    const messageController = threadControllers?.get(messageId);
    if (!threadControllers || !messageController) return null;
    if (messageController.frameId !== null) {
      cancelFrame(messageController.frameId);
    }
    threadControllers.delete(messageId);
    if (threadControllers.size === 0) {
      controllersByThreadRef.current.delete(threadId);
    }
    if (!messageController.buffer) return null;
    return {
      ...messageController.metadata,
      content: messageController.buffer,
    };
  }

  function tick(threadId: string | null, messageId: string) {
    const messageController = controllersByThreadRef.current
      .get(threadId)
      ?.get(messageId);
    if (!messageController) return;
    messageController.frameId = null;

    const now = performance.now();
    if (now > messageController.lastFrameAt) {
      const elapsed = Math.min(now - messageController.lastFrameAt, 64);
      messageController.lastFrameAt = now;
      const targetRate = Math.max(
        MIN_CHARS_PER_SECOND,
        messageController.arrivalRate,
        (messageController.buffer.length * 1000) / CATCH_UP_MS,
      );
      if (messageController.rate === 0) messageController.rate = targetRate;
      messageController.rate +=
        (targetRate - messageController.rate) *
        (1 - Math.exp(-elapsed / RATE_ADJUST_MS));
      messageController.credit += (messageController.rate * elapsed) / 1000;

      const budget = Math.floor(messageController.credit);
      if (budget > 0) {
        const part = takeFromBuffer(messageController.buffer, budget);
        messageController.buffer = part.rest;
        messageController.credit -= part.emitted.length;
        if (part.emitted) {
          appendRef.current([
            { ...messageController.metadata, content: part.emitted },
          ]);
        }
      }
    }

    if (messageController.buffer) {
      messageController.frameId = scheduleFrame(() =>
        tick(threadId, messageId),
      );
    } else {
      const threadControllers = controllersByThreadRef.current.get(threadId);
      threadControllers?.delete(messageId);
      if (threadControllers?.size === 0) {
        controllersByThreadRef.current.delete(threadId);
      }
    }
  }

  function pushChunk(chunk: StreamTextChunk) {
    const reduceMotion = window.matchMedia?.(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    if (reduceMotion || !chunk.content) {
      const buffered = flushMessage(chunk.threadId, chunk.messageId);
      appendRef.current(buffered ? [buffered, chunk] : [chunk]);
      return;
    }

    let threadControllers = controllersByThreadRef.current.get(chunk.threadId);
    if (!threadControllers) {
      threadControllers = new Map();
      controllersByThreadRef.current.set(chunk.threadId, threadControllers);
    }
    let messageController = threadControllers.get(chunk.messageId);
    const now = performance.now();
    if (!messageController) {
      messageController = {
        metadata: {
          messageId: chunk.messageId,
          threadId: chunk.threadId,
          runId: chunk.runId,
          createdAt: chunk.createdAt,
        },
        buffer: "",
        frameId: null,
        lastFrameAt: now + START_BUFFER_MS,
        sampleAt: now,
        sampleChars: 0,
        arrivalRate: 0,
        rate: 0,
        credit: 0,
      };
      threadControllers.set(chunk.messageId, messageController);
      appendRef.current([{ ...messageController.metadata, content: "" }]);
    } else {
      messageController.metadata = {
        messageId: chunk.messageId,
        threadId: chunk.threadId,
        runId: chunk.runId,
        createdAt: chunk.createdAt,
      };
    }

    messageController.buffer += chunk.content;
    messageController.sampleChars += chunk.content.length;
    const sampleMs = now - messageController.sampleAt;
    if (sampleMs >= RATE_SAMPLE_MS) {
      const observedRate = (messageController.sampleChars * 1000) / sampleMs;
      const weight = 1 - Math.exp(-sampleMs / RATE_ADJUST_MS);
      messageController.arrivalRate +=
        (observedRate - messageController.arrivalRate) * weight;
      messageController.sampleChars = 0;
      messageController.sampleAt = now;
    }
    if (messageController.frameId === null) {
      messageController.frameId = scheduleFrame(() =>
        tick(chunk.threadId, chunk.messageId),
      );
    }
  }

  function flushThread(threadId: string | null) {
    const threadControllers = controllersByThreadRef.current.get(threadId);
    if (!threadControllers) return;
    const chunks = [...threadControllers.keys()]
      .map((messageId) => flushMessage(threadId, messageId))
      .filter((chunk): chunk is StreamTextChunk => chunk !== null);
    if (chunks.length) appendRef.current(chunks);
  }

  function reset(threadId?: string | null) {
    for (const [id, threadControllers] of controllersByThreadRef.current) {
      if (threadId !== undefined && id !== threadId) continue;
      for (const messageController of threadControllers.values()) {
        if (messageController.frameId !== null) {
          cancelFrame(messageController.frameId);
        }
      }
      controllersByThreadRef.current.delete(id);
    }
  }

  useEffect(() => () => reset(), []);

  return { pushChunk, flushThread, reset };
}
