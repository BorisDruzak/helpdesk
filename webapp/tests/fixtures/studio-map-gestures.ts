import { expect, type Locator, type Page } from "playwright/test";

async function center(handle: Locator) {
  return handle.evaluate(element => {
    const bounds = element.getBoundingClientRect();
    const x = bounds.x + bounds.width / 2;
    const y = bounds.y + bounds.height / 2;
    return { x, y, hit: element.contains(document.elementFromPoint(x, y)) };
  });
}

export async function dragStudioHandles(page: Page, source: Locator, target: Locator) {
  let previous = "";
  await expect.poll(async () => {
    const [from, to] = await Promise.all([center(source), center(target)]);
    const current = JSON.stringify([from, to].map(point => [Math.round(point.x), Math.round(point.y)]));
    const stable = from.hit && to.hit && current === previous;
    previous = from.hit && to.hit ? current : "";
    return stable;
  }).toBe(true);

  const from = await center(source);
  await page.mouse.move(from.x, from.y);
  await page.mouse.down();
  try {
    const to = await center(target);
    await page.mouse.move(to.x, to.y, { steps: 20 });
    const finalTarget = await center(target);
    await page.mouse.move(finalTarget.x, finalTarget.y);
  } finally {
    await page.mouse.up();
  }
}
