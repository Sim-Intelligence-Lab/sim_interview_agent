"""Record a demo of Interview Studio as a GIF.

Drives the running app (http://127.0.0.1:5050) in Chrome with Playwright,
captures frames with Chrome's screencast, and assembles a GIF with Pillow.
Needs Google Chrome plus: pip install playwright pillow
Usage: python scripts/record_demo.py docs/demo.gif
"""

import base64
import io
import sys
import time

from PIL import Image
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:5050/"
VIEWPORT = {"width": 1280, "height": 1000}
GIF_WIDTH = 960
MIN_FRAME_MS = 80  # cap at ~12 fps

# A visible cursor, since headless screenshots don't show the real one.
CURSOR_JS = """
window.addEventListener('DOMContentLoaded', () => {
  const c = document.createElement('div');
  c.id = 'demo-cursor';
  c.innerHTML = '<svg width="26" height="26" viewBox="0 0 24 24"><path d="M4 2l16 9-7 2-3 7z" fill="#140206" stroke="#fff" stroke-width="1.5" stroke-linejoin="round"/></svg>';
  Object.assign(c.style, {position:'fixed', left:'-40px', top:'-40px', zIndex:2147483647, pointerEvents:'none', transition:'transform .12s'});
  document.body.appendChild(c);
  addEventListener('mousemove', e => { c.style.left = e.clientX - 4 + 'px'; c.style.top = e.clientY - 2 + 'px'; });
  addEventListener('mousedown', () => { c.style.transform = 'scale(.8)'; });
  addEventListener('mouseup', () => { c.style.transform = 'scale(1)'; });
});
"""


def main(output):
    frames = []  # (timestamp, jpeg bytes)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport=VIEWPORT, device_scale_factor=1)
        page.add_init_script(CURSOR_JS)
        page.goto(URL)
        page.wait_for_selector(".person-option.selected")
        page.wait_for_timeout(800)  # fonts settle

        cdp = page.context.new_cdp_session(page)

        def on_frame(event):
            frames.append((event["metadata"]["timestamp"], base64.b64decode(event["data"])))
            cdp.send("Page.screencastFrameAck", {"sessionId": event["sessionId"]})

        cdp.on("Page.screencastFrame", on_frame)
        cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 90,
                                          "maxWidth": VIEWPORT["width"], "maxHeight": VIEWPORT["height"]})
        page.mouse.move(640, 300)

        def click(locator, pause=600):
            box = locator.bounding_box()
            page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=28)
            page.wait_for_timeout(250)
            locator.click()
            page.wait_for_timeout(pause)

        def smooth_scroll(selector, delta, ms=1200):
            page.evaluate("""([sel, delta, ms]) => new Promise(done => {
                const el = sel ? document.querySelector(sel) : document.scrollingElement;
                const start = el.scrollTop, t0 = performance.now();
                const step = now => {
                  const k = Math.min(1, (now - t0) / ms), ease = k < .5 ? 2*k*k : 1 - Math.pow(-2*k + 2, 2) / 2;
                  el.scrollTop = start + delta * ease;
                  k < 1 ? requestAnimationFrame(step) : done();
                };
                requestAnimationFrame(step);
            })""", [selector, delta, ms])

        # 1. Home page, then start the interview.
        page.wait_for_timeout(1600)
        click(page.locator("#start"), pause=1200)

        # 2. Pick the law clinic question from the list, then ask it.
        click(page.locator(".question-item").nth(11), pause=900)
        click(page.locator("#ask"), pause=300)

        # 3. Trang thinks (real Ollama call), then answers while her mouth moves.
        page.wait_for_selector(".answer-card", timeout=180_000)
        page.wait_for_function("!document.getElementById('interview').classList.contains('speaking')",
                               timeout=60_000)
        page.wait_for_timeout(1000)

        # 4. Show the scored memories under the answer.
        smooth_scroll("#answer-area", 330, 1400)
        page.wait_for_timeout(1300)

        # 5. Scroll down to "How Trang answered" and open the prompt and raw reply.
        trace_top = page.evaluate("document.querySelector('.trace-window').getBoundingClientRect().top - 16")
        smooth_scroll(None, trace_top, 1500)
        page.wait_for_timeout(1300)
        click(page.locator(".trace-code summary").nth(0), pause=900)
        smooth_scroll(".trace-code pre", 260, 1600)
        page.wait_for_timeout(500)
        click(page.locator(".trace-code summary").nth(1), pause=600)
        smooth_scroll(None, 320, 1200)
        page.wait_for_timeout(2200)

        cdp.send("Page.stopScreencast")
        time.sleep(0.3)
        browser.close()

    build_gif(frames, output)


def build_gif(frames, output):
    # Merge frames closer than MIN_FRAME_MS, keeping each one's on-screen time.
    kept = []
    for i, (stamp, data) in enumerate(frames):
        nxt = frames[i + 1][0] if i + 1 < len(frames) else stamp + 2.0
        ms = max(20, round((nxt - stamp) * 1000))
        if kept and kept[-1][1] < MIN_FRAME_MS:
            kept[-1] = (data, kept[-1][1] + ms)
        else:
            kept.append((data, ms))

    images = []
    for data, _ in kept:
        img = Image.open(io.BytesIO(data)).convert("RGB")
        height = round(img.height * GIF_WIDTH / img.width)
        images.append(img.resize((GIF_WIDTH, height), Image.LANCZOS))

    # One shared palette for every frame: smaller file, no colour flicker.
    sample = images[:: max(1, len(images) // 12)]
    sheet = Image.new("RGB", (GIF_WIDTH, sample[0].height * len(sample)))
    for n, img in enumerate(sample):
        sheet.paste(img, (0, n * img.height))
    palette = sheet.quantize(colors=256, method=Image.Quantize.MEDIANCUT)
    paletted = [img.quantize(palette=palette, dither=Image.Dither.NONE) for img in images]

    durations = [ms for _, ms in kept]
    paletted[0].save(output, save_all=True, append_images=paletted[1:], duration=durations,
                     loop=0, optimize=True, disposal=1)
    total = sum(durations) / 1000
    print(f"{len(paletted)} frames, {total:.1f} s -> {output}")


if __name__ == "__main__":
    main(sys.argv[1])
