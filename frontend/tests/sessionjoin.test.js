// "Do you attend this session?" (spec 034) and its festival shape (spec 056).
//
// A regular session asks one question before joining: local, or just visiting. A
// festival year asks nothing: nobody is local to a festival, and adding one is about
// having its days on Home, so "Yes, Add Me" joins as a member at once.
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

  it("asks a festival's joiner nothing and joins them as a member", async () => {
    render(SessionJoin, { sessionPath: "oflahertys/2026", isFestival: true });
    expect(screen.getByText("Are you at this festival?")).toBeInTheDocument();
    expect(
      screen.queryByText("Do you attend this session?"),
    ).not.toBeInTheDocument();

    await fireEvent.click(addMe());
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(
      screen.queryByText("Are you a local, or just visiting?"),
    ).not.toBeInTheDocument();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/sessions/oflahertys/2026/join");
    expect(JSON.parse(init.body)).toEqual({ relationship: "member" });
  });
});
