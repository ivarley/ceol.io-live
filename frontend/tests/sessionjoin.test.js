// "Do you attend this session?" (spec 034): a regular session asks one question before
// joining, local or just visiting. (A festival year's prompt is the banner under its
// band, festivaljoinbanner.test.js.)
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, fireEvent, waitFor, screen } from "@testing-library/svelte";
import SessionJoin from "../src/sessionpage/SessionJoin.svelte";

let fetchMock;

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["setTimeout"] }); // the post-join reload never fires
  fetchMock = vi
    .fn()
    .mockResolvedValue({ ok: true, json: async () => ({ success: true }) });
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

const addMe = () => screen.getByRole("button", { name: "Yes, Add Me" });

describe("SessionJoin", () => {
  it("asks a regular session's joiner whether they are local, then joins as they answer", async () => {
    render(SessionJoin, { sessionPath: "austin/mueller" });
    expect(screen.getByText("Do you attend this session?")).toBeInTheDocument();
    await fireEvent.click(addMe());
    expect(
      screen.getByText("Are you a local, or just visiting?"),
    ).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();

    await fireEvent.click(screen.getByText("Just visiting"));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/sessions/austin/mueller/join");
    expect(JSON.parse(init.body)).toEqual({ relationship: "visitor" });
  });
});
