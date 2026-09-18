import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import "@/test/browserStubs";
import { MessageInput } from "@/pages/chat/components/MessageInput";

describe("MessageInput action menu", () => {
  it("closes on Escape and outside clicks", () => {
    render(
      <MessageInput
        draft=""
        setDraft={vi.fn()}
        attachments={[]}
        uploading={0}
        running={false}
        disabled={false}
        modelId=""
        models={[]}
        modelsLoading={false}
        placement="bottom"
        selectModel={vi.fn()}
        upload={vi.fn()}
        removeAttachment={vi.fn()}
        submit={vi.fn()}
        cancel={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Action menu" }));
    expect(screen.getByRole("menu", { name: "Actions menu" })).toBeTruthy();

    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("menu")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Action menu" }));
    fireEvent.click(document.body);
    expect(screen.queryByRole("menu")).toBeNull();
  });
});
