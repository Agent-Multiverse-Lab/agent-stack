import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/test/browserStubs";
import { AgentMessageComposer } from "@/pages/chat/components/AgentMessageComposer";

const baseProps = {
  draft: "",
  setDraft: vi.fn(),
  attachments: [],
  uploading: 0,
  running: false,
  disabled: false,
  modelId: "",
  models: [],
  modelsLoading: false,
  placement: "bottom" as const,
  selectModel: vi.fn(),
  upload: vi.fn(),
  removeAttachment: vi.fn(),
  submit: vi.fn(),
  cancel: vi.fn(),
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  Reflect.deleteProperty(window, "SpeechRecognition");
  Reflect.deleteProperty(window, "webkitSpeechRecognition");
});

describe("AgentMessageComposer", () => {
  it("opens the shadcn action menu and closes it on Escape or outside click", () => {
    render(<AgentMessageComposer {...baseProps} />);

    fireEvent.click(screen.getByRole("button", { name: "Action menu" }));
    const menu = screen.getByRole("menu", { name: "Action menu" });
    expect(menu.className).toContain("w-(--anchor-width)");
    expect(menu.className).not.toContain("w-52");

    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("menu")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Action menu" }));
    fireEvent.pointerDown(document.body);
    expect(screen.queryByRole("menu")).toBeNull();
  });

  it("submits with Enter and preserves Shift+Enter for a new line", () => {
    const submit = vi.fn();
    render(
      <AgentMessageComposer {...baseProps} draft="Inspect this" submit={submit} />,
    );
    const editor = screen.getByRole("textbox", { name: "Message" });

    fireEvent.keyDown(editor, { key: "Enter", shiftKey: true });
    expect(submit).not.toHaveBeenCalled();

    fireEvent.keyDown(editor, { key: "Enter" });
    expect(submit).toHaveBeenCalledOnce();
  });

  it("keeps IME composition from submitting and cancels an active run", () => {
    const submit = vi.fn();
    const cancel = vi.fn();
    const { rerender } = render(
      <AgentMessageComposer {...baseProps} draft="你好" submit={submit} />,
    );
    const editor = screen.getByRole("textbox", { name: "Message" });

    fireEvent.compositionStart(editor);
    fireEvent.keyDown(editor, { key: "Enter" });
    expect(submit).not.toHaveBeenCalled();

    rerender(
      <AgentMessageComposer
        {...baseProps}
        draft="你好"
        running
        submit={submit}
        cancel={cancel}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Cancel response" }));
    expect(cancel).toHaveBeenCalledOnce();
  });

  it("moves controls below a multiline draft", () => {
    render(<AgentMessageComposer {...baseProps} draft={"First\nSecond"} />);

    expect(
      screen
        .getByRole("form", { name: "Agent message composer" })
        .getAttribute("data-expanded"),
    ).toBe("true");
  });

  it("uses native browser dictation and appends recognized speech", () => {
    class FakeSpeechRecognition {
      continuous = false;
      interimResults = false;
      lang = "";
      onresult: ((event: {
        results: ArrayLike<{ 0: { transcript: string }; length: number }>;
      }) => void) | null = null;
      onend: (() => void) | null = null;
      onerror: (() => void) | null = null;
      start = vi.fn();
      stop = vi.fn();
      abort = vi.fn();

      constructor() {
        speechInstances.push(this);
      }
    }

    const speechInstances: FakeSpeechRecognition[] = [];

    Object.defineProperty(window, "SpeechRecognition", {
      configurable: true,
      value: FakeSpeechRecognition,
    });

    const setDraft = vi.fn();
    render(
      <AgentMessageComposer
        {...baseProps}
        draft="Existing"
        setDraft={setDraft}
      />,
    );
    const speech = speechInstances[0];

    fireEvent.click(screen.getByRole("button", { name: "Start dictation" }));
    expect(speech?.start).toHaveBeenCalledOnce();

    act(() => {
      speech?.onresult?.({
        results: [{ 0: { transcript: "spoken words" }, length: 1 }],
      });
    });
    expect(setDraft).toHaveBeenCalledWith("Existing spoken words");

    fireEvent.click(screen.getByRole("button", { name: "Stop dictation" }));
    expect(speech?.stop).toHaveBeenCalledOnce();
  });

  it("runs the spectrum sweep after selecting a different model", () => {
    const selectModel = vi.fn();
    render(
      <AgentMessageComposer
        {...baseProps}
        modelId="first"
        selectModel={selectModel}
        models={[
          {
            id: "first",
            name: "First",
            display_name: "First",
            version: "1",
            provider: "test",
            icon: "",
            is_available: true,
            is_default: true,
            is_fallback: false,
            is_flash: false,
          },
          {
            id: "second",
            name: "Second",
            display_name: "Second",
            version: "2",
            provider: "test",
            icon: "",
            is_available: true,
            is_default: false,
            is_fallback: false,
            is_flash: false,
          },
        ]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Select model" }));
    fireEvent.click(screen.getByRole("menuitemradio", { name: /Second/ }));

    expect(selectModel).toHaveBeenCalledWith("second");
    expect(document.querySelector("[data-model-sweep]")).toBeTruthy();
  });
});
