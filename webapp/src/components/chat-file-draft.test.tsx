import { createEvent, fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { useChatFileDrop } from "./chat-file-draft";

function setup(disabled = false) {
  const upload = vi.fn();
  function Chat() {
    const {handlers} = useChatFileDrop(disabled, upload);
    return <section {...handlers}><textarea aria-label="Ответ" defaultValue="Мой черновик" /></section>;
  }
  render(<Chat />);
  return {upload, input: screen.getByRole("textbox", {name: "Ответ"})};
}
function paste(input: HTMLElement, files: File[], text = "", items = files.map(file => ({kind: "file", getAsFile: () => file}))) {
  const event = createEvent.paste(input, {clipboardData: {files, items, getData: (type: string) => type === "text/plain" ? text : ""}});
  fireEvent(input, event);
  return event;
}
const png = () => new File(["image"], "image.png", {type: "image/png"});

it("attaches clipboard screenshots once without replacing existing reply text", () => {
  const {upload, input} = setup(); const images = [png(), png()];
  expect(paste(input, images).defaultPrevented).toBe(true);
  expect(upload).toHaveBeenCalledExactlyOnceWith(images);
  expect(input).toHaveValue("Мой черновик");
});
it("keeps native text insertion when clipboard contains both text and an image", () => {
  const {upload, input} = setup(); const image = png();
  expect(paste(input, [image], "Вставленный текст").defaultPrevented).toBe(false);
  expect(upload).toHaveBeenCalledExactlyOnceWith([image]);
});
it("leaves text and HTML-only image links to normal text paste without uploading", () => {
  const {upload, input} = setup();
  expect(paste(input, [], "Обычный текст").defaultPrevented).toBe(false);
  const event = createEvent.paste(input, {clipboardData: {files: [], items: [], getData: () => '<img src="https://example.invalid/picture.png">'}});
  fireEvent(input, event);
  expect(event.defaultPrevented).toBe(false);
  expect(upload).not.toHaveBeenCalled();
});
it("supports clipboard files fallback and ignores non-image files", () => {
  const {upload, input} = setup(); const image = png();
  paste(input, [image, new File(["text"], "log.txt", {type: "text/plain"})], "", []);
  expect(upload).toHaveBeenCalledExactlyOnceWith([image]);
});
it("does not attach clipboard images when replying is disabled", () => {
  const {upload, input} = setup(true);
  expect(paste(input, [png()]).defaultPrevented).toBe(true);
  expect(upload).not.toHaveBeenCalled();
});
