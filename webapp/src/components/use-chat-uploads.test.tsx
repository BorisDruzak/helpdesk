import { act, renderHook, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { useChatUploads } from "./use-chat-uploads";

const file = (name: string) => new File([name], name);
function deferred() { let resolve!: (value: string) => void; const promise = new Promise<string>(done => { resolve = done; }); return {promise, resolve}; }
it("queues repeated drops, preserves partial success and reports the failed filename", async () => {
  const first = deferred(); const received = vi.fn(); const error = vi.fn();
  const upload = vi.fn(async (item: File) => {
    if (item.name === "shot.png") return first.promise;
    if (item.name === "bad.txt") throw new Error("Ошибка загрузки");
    return item.name;
  });
  const {result} = renderHook(() => useChatUploads({scope: "ticket:public", enabled: true, upload, onUploaded: received, onStart: vi.fn(), onError: error, errorMessage: () => "Ошибка загрузки"}));
  act(() => result.current.addFiles([file("shot.png"), file("bad.txt")]));
  act(() => result.current.addFiles([file("log.txt")]));
  expect(upload).toHaveBeenCalledTimes(1);
  expect(result.current.uploading).toBe(true);
  await act(async () => first.resolve("image-id"));
  await waitFor(() => expect(result.current.uploading).toBe(false));
  expect(upload.mock.calls.map(([item]) => item.name)).toEqual(["shot.png", "bad.txt", "log.txt"]);
  expect(received.mock.calls.map(([value]) => value)).toEqual(["image-id", "log.txt"]);
  expect(error).toHaveBeenCalledWith("bad.txt: Ошибка загрузки");
});
it("does not transfer a late upload or queued files into a different ticket or audience", async () => {
  const late = deferred(); const received = vi.fn(); const upload = vi.fn(async (item: File) => item.name === "old.png" ? late.promise : item.name);
  const {result, rerender} = renderHook(({scope}) => useChatUploads({scope, enabled: true, upload, onUploaded: received, onStart: vi.fn(), onError: vi.fn(), errorMessage: () => "Ошибка"}), {initialProps: {scope: "one:internal"}});
  act(() => result.current.addFiles([file("old.png"), file("not-started.txt")]));
  rerender({scope: "two:public"});
  act(() => result.current.addFiles([file("new.png")]));
  await waitFor(() => expect(received).toHaveBeenCalledWith("new.png", expect.any(File)));
  await act(async () => late.resolve("PRIVATE-OLD-ID"));
  expect(received).toHaveBeenCalledTimes(1);
  expect(upload.mock.calls.map(([item]) => item.name)).toEqual(["old.png", "new.png"]);
});
it("blocks disabled uploads and discards late results after permission loss or unmount", async () => {
  const late = deferred(); const received = vi.fn(); const upload = vi.fn(() => late.promise);
  const {result, rerender, unmount} = renderHook(({enabled}) => useChatUploads({scope: "ticket", enabled, upload, onUploaded: received, onStart: vi.fn(), onError: vi.fn(), errorMessage: () => "Ошибка"}), {initialProps: {enabled: false}});
  act(() => result.current.addFiles([file("denied.png")])); expect(upload).not.toHaveBeenCalled();
  rerender({enabled: true}); act(() => result.current.addFiles([file("late.png")]));
  rerender({enabled: false}); unmount();
  await act(async () => late.resolve("discarded"));
  expect(received).not.toHaveBeenCalled();
});
