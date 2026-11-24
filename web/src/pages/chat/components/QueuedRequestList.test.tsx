import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";

import type { QueuedRunRequestItem } from "@/api/thread";
import {
  QueuedRequestList,
  type QueuedRequestListProps,
} from "@/pages/chat/components/QueuedRequestList";

vi.mock("@/i18n", () => ({
  useTranslation: () => ({ t: (value: string) => value }),
}));

const makeItem = (
  overrides: Partial<QueuedRunRequestItem> = {},
): QueuedRunRequestItem => ({
  request_id: "req-1",
  dispatch_policy: "enqueue",
  queue_seq: 1,
  content: "First queued prompt",
  created_at: "2026-11-24T00:00:00Z",
  ...overrides,
});

const baseProps: QueuedRequestListProps = {
  requests: [makeItem()],
  isActive: true,
  hasPendingInteraction: false,
  isSubmitting: false,
  onSteer: vi.fn(),
  onRemove: vi.fn(),
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("QueuedRequestList", () => {
  it("renders nothing when requests is empty", () => {
    const { container } = render(
      <QueuedRequestList {...baseProps} requests={[]} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders count, policy badges, content, and attachment fallback", () => {
    render(
      <QueuedRequestList
        {...baseProps}
        requests={[
          makeItem({
            request_id: "req-1",
            dispatch_policy: "enqueue",
            content: "Check logs",
          }),
          makeItem({
            request_id: "req-2",
            dispatch_policy: "steer",
            queue_seq: 2,
            content: "",
          }),
        ]}
      />,
    );

    const toggle = screen.getByRole("button", {
      name: "Collapse waiting requests",
    });
    expect(within(toggle).getByText("Waiting requests")).toBeTruthy();
    expect(within(toggle).getByText("2")).toBeTruthy();
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(within(items[0]).getByText("Queued")).toBeTruthy();
    expect(within(items[0]).getByText("Check logs")).toBeTruthy();
    expect(within(items[1]).getByText("Steer")).toBeTruthy();
    expect(within(items[1]).getByText("Attachment")).toBeTruthy();
  });

  it("shows Steer only for non-steer items when active and triggers callbacks", () => {
    const onSteer = vi.fn();
    const onRemove = vi.fn();

    render(
      <QueuedRequestList
        {...baseProps}
        isActive={true}
        onSteer={onSteer}
        onRemove={onRemove}
        requests={[
          makeItem({
            request_id: "req-enqueue",
            dispatch_policy: "enqueue",
            content: "Queued prompt",
          }),
          makeItem({
            request_id: "req-steer",
            dispatch_policy: "steer",
            queue_seq: 2,
            content: "Steered prompt",
          }),
        ]}
      />,
    );

    const steerButtons = screen.getAllByRole("button", { name: "Steer" });
    expect(steerButtons).toHaveLength(1);

    fireEvent.click(steerButtons[0]);
    expect(onSteer).toHaveBeenCalledWith("req-enqueue");

    const removeButtons = screen.getAllByRole("button", { name: "Remove" });
    expect(removeButtons).toHaveLength(2);
    fireEvent.click(removeButtons[1]);
    expect(onRemove).toHaveBeenCalledWith("req-steer");
  });

  it("handles idle Run now visibility and disabled state", () => {
    const requests = [
      makeItem({
        request_id: "req-1",
        dispatch_policy: "enqueue",
        content: "Queued one",
      }),
      makeItem({
        request_id: "req-2",
        dispatch_policy: "steer",
        queue_seq: 2,
        content: "Steered two",
      }),
    ];

    const { rerender } = render(
      <QueuedRequestList
        {...baseProps}
        requests={requests}
        isActive={false}
        hasPendingInteraction={false}
        isSubmitting={false}
      />,
    );

    const runNowButtons = screen.getAllByRole("button", { name: "Run now" });
    expect(runNowButtons).toHaveLength(2);
    expect((runNowButtons[0] as HTMLButtonElement).disabled).toBe(false);

    rerender(
      <QueuedRequestList
        {...baseProps}
        requests={requests}
        isActive={false}
        hasPendingInteraction={false}
        isSubmitting={true}
      />,
    );

    screen
      .getAllByRole("button", { name: "Run now" })
      .forEach((button) => expect((button as HTMLButtonElement).disabled).toBe(true));

    rerender(
      <QueuedRequestList
        {...baseProps}
        requests={requests}
        isActive={false}
        hasPendingInteraction={true}
        isSubmitting={false}
      />,
    );

    expect(screen.queryByRole("button", { name: "Run now" })).toBeNull();
  });

  it("collapses and re-expands the waiting request list", () => {
    render(
      <QueuedRequestList
        {...baseProps}
        requests={[makeItem({ content: "Collapsible item" })]}
      />,
    );

    expect(screen.getByText("Collapsible item")).toBeTruthy();

    fireEvent.click(
      screen.getByRole("button", { name: "Collapse waiting requests" }),
    );
    expect(screen.queryByText("Collapsible item")).toBeNull();

    fireEvent.click(
      screen.getByRole("button", { name: "Expand waiting requests" }),
    );
    expect(screen.getByText("Collapsible item")).toBeTruthy();
  });
});
