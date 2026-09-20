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
  it("opens the file picker from the action menu and uploads selected files", () => {
    const upload = vi.fn();
    const { container } = render(<AgentMessageComposer {...baseProps} upload={upload} />);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const openPicker = vi.spyOn(input, "click");

    fireEvent.click(screen.getByRole("button", { name: "Action menu" }));
    expect(
      screen.getByRole("menuitem", { name: /Connectors/ }).getAttribute("aria-disabled"),
    ).toBe("true");
    fireEvent.click(screen.getByRole("menuitem", { name: /Add attachment/ }));
    expect(openPicker).toHaveBeenCalledOnce();

    const file = new File(["hello"], "notes.txt", { type: "text/plain" });
    fireEvent.change(input, { target: { files: [file] } });
    expect(upload).toHaveBeenCalledWith([file]);
  });

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

  it("shrinks a long draft back to one line and resets after clearing", () => {
    const { rerender } = render(<AgentMessageComposer {...baseProps} />);
    const editor = screen.getByRole("textbox", { name: "Message" }) as HTMLTextAreaElement;
    const composer = screen.getByRole("form", { name: "Agent message composer" });
    // jsdom has no layout engine; supply the heights of rendered text.
    let contentHeight = 400;
    Object.defineProperty(editor, "scrollHeight", { get: () => contentHeight });

    rerender(<AgentMessageComposer {...baseProps} draft={"Long line\n".repeat(20)} />);
    expect(editor.style.height).toBe("160px");
    expect(editor.style.overflowY).toBe("auto");
    expect(composer.getAttribute("data-expanded")).toBe("true");

    contentHeight = 88;
    rerender(<AgentMessageComposer {...baseProps} draft={"One\nTwo\nThree"} />);
    expect(editor.style.height).toBe("88px");
    expect(editor.style.overflowY).toBe("hidden");

    contentHeight = 40;
    rerender(<AgentMessageComposer {...baseProps} draft="Short" />);
    expect(editor.style.height).toBe("40px");
    expect(composer.getAttribute("data-expanded")).toBe("false");

    contentHeight = 400;
    rerender(<AgentMessageComposer {...baseProps} draft={"Long line\n".repeat(20)} />);
    rerender(<AgentMessageComposer {...baseProps} draft="" />);
    expect(editor.style.height).toBe("40px");
    expect(editor.style.overflowY).toBe("hidden");
    expect(composer.getAttribute("data-expanded")).toBe("false");
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
