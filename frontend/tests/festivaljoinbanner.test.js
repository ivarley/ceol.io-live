// "Are you at {festival}?" (spec 056): the festival year's join prompt, a strip under
// the band of the year's page and of each of its nights. One tap joins as a member, with
// no local-or-visiting question; signed out, it goes to sign-in and back here.
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, fireEvent, waitFor, screen } from "@testing-library/svelte";
import FestivalJoinBanner from "../src/shared/FestivalJoinBanner.svelte";

let fetchMock;

beforeEach(() => {
  fetchMock = vi
    .fn()
    .mockResolvedValue({ ok: true, json: async () => ({ success: true }) });
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("FestivalJoinBanner", () => {
  it("names the festival and joins as a member in one tap", async () => {
    const onJoined = vi.fn();
    render(FestivalJoinBanner, {
      sessionPath: "oflahertys/2026",
      name: "O'Flaherty's Irish Music Retreat 2026",
      signedIn: true,
      onJoined,
    });
    expect(
      screen.getByText("Are you at O'Flaherty's Irish Music Retreat 2026?"),
    ).toBeInTheDocument();
    await fireEvent.click(screen.getByRole("button"));
    await waitFor(() => expect(onJoined).toHaveBeenCalledTimes(1));
    expect(
      screen.queryByText("Are you a local, or just visiting?"),
    ).not.toBeInTheDocument();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/sessions/oflahertys/2026/join");
    expect(JSON.parse(init.body)).toEqual({ relationship: "member" });
  });

  it("stays, and says so, when the server refuses", async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      json: async () => ({ success: false, message: "no" }),
    });
    const onJoined = vi.fn();
    render(FestivalJoinBanner, {
      sessionPath: "oflahertys/2026",
      name: "Fest",
      signedIn: true,
      onJoined,
    });
    await fireEvent.click(screen.getByRole("button"));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(onJoined).not.toHaveBeenCalled();
    expect(screen.getByRole("button")).not.toBeDisabled();
  });

  it("sends a signed-out viewer to sign in, and back to this page", () => {
    render(FestivalJoinBanner, {
      sessionPath: "oflahertys/2026",
      name: "Fest",
      signedIn: false,
    });
    const link = screen.getByRole("link");
    expect(link.getAttribute("href")).toBe(
      `/login?next=${encodeURIComponent(location.pathname + location.search)}`,
    );
    expect(
      screen.getByText("Sign in to add it to your sessions"),
    ).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
