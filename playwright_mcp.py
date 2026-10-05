import asyncio
import json
import sys

from playwright.async_api import async_playwright # pyright: ignore[reportMissingImports]
from fastmcp.server import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.utilities.types import Image

# This server speaks MCP over stdio, where stdout IS the JSON-RPC channel.
# Never print() to stdout from anywhere in this file - one stray line corrupts
# the stream and drops the client connection. Diagnostics go to stderr.

playwright_instance = None
browser = None
context = None
page = None

# Guards browser startup: MCP clients issue tool calls concurrently, and a
# plain "if browser is None" check lets two of them launch two browsers and
# leak one of the Chromium processes.
_startup_lock = asyncio.Lock()

# Session file loaded into the next browser context, set by load_session().
_storage_state_path = None

mcp = FastMCP("Playwright-MCP-Server")

DEFAULT_TIMEOUT = 15000


def _fail(action: str, exc: Exception):
    """Surface a failure as a real MCP error rather than a normal string.

    Returning "Failed to ..." as ordinary text makes every call look like a
    success to the client; ToolError sets isError so callers can branch on it.
    """
    detail = f"{type(exc).__name__}: {exc}".strip()
    raise ToolError(f"{action} - {detail[:900]}") from exc


def _is_navigation_error(exc: Exception) -> bool:
    """True for the transient errors a navigation landing mid-call produces."""
    msg = str(exc).lower()
    return any(s in msg for s in (
        "execution context was destroyed",
        "execution context is not available",
        "cannot find context with specified id",
        "frame was detached",
        "because of a navigation",
    ))


async def _retry_nav(fn, attempts: int = 3):
    """Run an evaluate that may collide with an in-flight navigation.

    Clicking something and immediately reading the page is an ordinary thing to
    do; without this, every such call dies with "Execution context was
    destroyed" and each caller has to write its own retry. Only navigation
    errors are retried - a genuine script error still raises on the first try.
    """
    last = None
    for i in range(attempts):
        try:
            return await fn()
        except Exception as e:
            if not _is_navigation_error(e):
                raise
            last = e
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=10000)
            except Exception:
                pass
            await asyncio.sleep(0.4 * (i + 1))
    raise last


async def open_browser() -> None:
    """Ensure the browser, context and page are initialized."""
    global playwright_instance, browser, context, page

    if page is not None and not page.is_closed():
        return

    async with _startup_lock:
        # Re-check inside the lock: another call may have won the race.
        if page is not None and not page.is_closed():
            return

        playwright_instance = await async_playwright().start()
        # --start-maximized opens the window full-screen, but Playwright still
        # pins a fixed 1280x720 viewport unless no_viewport is set, so the page
        # would not actually fill the window. Both are required.
        browser = await playwright_instance.chromium.launch(
            headless=False,
            args=["--start-maximized"],
        )
        context = await browser.new_context(
            no_viewport=True,
            storage_state=_storage_state_path,
        )
        context.set_default_timeout(DEFAULT_TIMEOUT)
        page = await context.new_page()


def _locator(selector: str, frame: str = "", strict: bool = False):
    """Resolve a selector to a Locator, optionally inside an iframe.

    strict=False keeps the historical behaviour of acting on the first match;
    strict=True raises if the selector is ambiguous, which is what you want in
    a regression suite.
    """
    root = page.frame_locator(frame) if frame else page
    loc = root.locator(selector)
    return loc if strict else loc.first


@mcp.tool()
async def navigate(url: str, wait_until: str = "domcontentloaded", timeout: int = DEFAULT_TIMEOUT) -> str:
    """Navigate to a given URL.

    wait_until: one of load, domcontentloaded, networkidle, commit. Prefer
    domcontentloaded - sites with long-lived analytics sockets never reach
    networkidle and it will simply time out.
    """
    try:
        await open_browser()
        await page.goto(url, wait_until=wait_until, timeout=timeout)
        return f"Navigated to {url}\nPage Title: {await page.title()}"
    except Exception as e:
        _fail(f"Failed to navigate to {url}", e)


@mcp.tool()
async def click(selector: str, frame: str = "", strict: bool = False,
                timeout: int = DEFAULT_TIMEOUT) -> str:
    """Click an element matching the given selector.

    Append :visible to the selector on pages that render hidden mobile and
    desktop duplicates of the same control, or the click waits on the hidden
    one and times out.
    """
    try:
        await open_browser()
        await _locator(selector, frame, strict).click(timeout=timeout)
        return f"Clicked element with selector: {selector}"
    except Exception as e:
        _fail(f"Failed to click element with selector {selector}", e)


@mcp.tool()
async def hover(selector: str, frame: str = "", strict: bool = False,
                timeout: int = DEFAULT_TIMEOUT) -> str:
    """Hover over an element - use for menus that open on hover, not click."""
    try:
        await open_browser()
        await _locator(selector, frame, strict).hover(timeout=timeout)
        return f"Hovered over element with selector: {selector}"
    except Exception as e:
        _fail(f"Failed to hover over element with selector {selector}", e)


@mcp.tool()
async def type_text(selector: str, value: str, use_keystrokes: bool = False,
                    delay: int = 50, frame: str = "", strict: bool = False,
                    timeout: int = DEFAULT_TIMEOUT) -> str:
    """Type text into an element matching the given selector.

    By default this uses fill(), which sets the value in one shot. Widgets that
    listen for real key events - search autocompletes, Knockout/React-bound
    inputs - often ignore that, so set use_keystrokes=True to send the value one
    character at a time instead.
    """
    try:
        await open_browser()
        loc = _locator(selector, frame, strict)
        if use_keystrokes:
            await loc.click(timeout=timeout)
            await loc.fill("")
            await loc.press_sequentially(value, delay=delay)
            how = "keystrokes"
        else:
            await loc.fill(value, timeout=timeout)
            how = "fill"
        return f"Typed text into element with selector: {selector} (via {how})"
    except Exception as e:
        _fail(f"Failed to type text into element with selector {selector}", e)


@mcp.tool()
async def press_key(key: str, selector: str = "", frame: str = "",
                    timeout: int = DEFAULT_TIMEOUT) -> str:
    """Press a keyboard key, e.g. Enter, Tab, Escape, ArrowDown, Control+A.

    Pass a selector to focus that element first; omit it to send the key to
    whatever currently has focus.
    """
    try:
        await open_browser()
        if selector:
            await _locator(selector, frame).press(key, timeout=timeout)
            return f"Pressed {key} on element with selector: {selector}"
        await page.keyboard.press(key)
        return f"Pressed {key}"
    except Exception as e:
        _fail(f"Failed to press key {key}", e)


@mcp.tool()
async def select_option(selector: str, value: str = "", label: str = "", index: int = -1,
                        frame: str = "", timeout: int = DEFAULT_TIMEOUT) -> str:
    """Choose an option in a <select> dropdown.

    Give exactly one of value (the option's value attribute), label (its visible
    text) or index (0-based). A plain click() cannot pick an option, and setting
    .value through JavaScript does not fire the change events that frameworks
    listen for - this does both correctly.
    """
    try:
        await open_browser()
        loc = _locator(selector, frame)
        if value:
            chosen, how = await loc.select_option(value=value, timeout=timeout), f"value={value}"
        elif label:
            chosen, how = await loc.select_option(label=label, timeout=timeout), f"label={label}"
        elif index >= 0:
            chosen, how = await loc.select_option(index=index, timeout=timeout), f"index={index}"
        else:
            raise ToolError("select_option needs one of value, label or index.")
        return f"Selected option ({how}) in {selector}. Resulting value(s): {chosen}"
    except ToolError:
        raise
    except Exception as e:
        _fail(f"Failed to select option in {selector}", e)


@mcp.tool()
async def wait_for_selector(selector: str, state: str = "visible", frame: str = "",
                            strict: bool = False, timeout: int = DEFAULT_TIMEOUT) -> str:
    """Wait until an element reaches a state: visible, hidden, attached, detached.

    With strict=False this waits on the FIRST match, so if a page carries a
    hidden duplicate of the element you will wait on the wrong one - add
    :visible to the selector, or set strict=True to catch the ambiguity.
    """
    try:
        await open_browser()
        await _locator(selector, frame, strict).wait_for(state=state, timeout=timeout)
        return f"Selector {selector} reached state '{state}'."
    except Exception as e:
        _fail(f"Timed out waiting for {selector} to be '{state}'", e)


@mcp.tool()
async def wait_for_load_state(state: str = "load", timeout: int = DEFAULT_TIMEOUT) -> str:
    """Wait for page load progress: load, domcontentloaded or networkidle.

    Use this after an action that triggers navigation or an AJAX update, since
    click() waits for the element but not for what happens afterwards.
    """
    try:
        await open_browser()
        await page.wait_for_load_state(state, timeout=timeout)
        return f"Page reached load state '{state}'. Current URL: {page.url}"
    except Exception as e:
        _fail(f"Timed out waiting for load state '{state}'", e)


@mcp.tool()
async def get_text(selector: str = "body", max_chars: int = 3000, frame: str = "",
                   timeout: int = DEFAULT_TIMEOUT) -> str:
    """Get the visible text of an element, defaulting to the whole page body."""
    try:
        await open_browser()
        text = await _locator(selector, frame).inner_text(timeout=timeout)
        if len(text) > max_chars:
            return (f"Text content of {selector} (truncated to {max_chars} chars):\n"
                    f"{text[:max_chars]}... (truncated)")
        return f"Text content of {selector}:\n{text}"
    except Exception as e:
        _fail(f"Failed to get text content of {selector}", e)


@mcp.tool()
async def get_attribute(selector: str, attribute: str, frame: str = "",
                        timeout: int = DEFAULT_TIMEOUT) -> str:
    """Read one attribute off an element, e.g. href, value, class, data-qty."""
    try:
        await open_browser()
        value = await _locator(selector, frame).get_attribute(attribute, timeout=timeout)
        if value is None:
            return f"Element {selector} has no attribute '{attribute}'."
        return f"{selector} [{attribute}] = {value}"
    except Exception as e:
        _fail(f"Failed to read attribute {attribute} from {selector}", e)


@mcp.tool()
async def page_info() -> str:
    """Current URL, title, viewport size and open tabs - cheaper than a screenshot."""
    try:
        await open_browser()
        size = await page.evaluate("() => ({w: window.innerWidth, h: window.innerHeight})")
        tabs = [{"index": i, "url": p.url, "active": p is page}
                for i, p in enumerate(context.pages)]
        return json.dumps({"url": page.url, "title": await page.title(),
                           "viewport": size, "tabs": tabs}, indent=2)
    except Exception as e:
        _fail("Failed to read page info", e)


@mcp.tool()
async def switch_tab(index: int) -> str:
    """Switch to another open tab by index, as listed by page_info.

    Clicking a target=_blank link or triggering a popup opens a new tab; every
    other tool keeps acting on the old one until you switch.
    """
    global page
    try:
        await open_browser()
        pages = context.pages
        if index < 0 or index >= len(pages):
            raise ToolError(f"No tab at index {index}. Open tabs: {len(pages)}.")
        page = pages[index]
        await page.bring_to_front()
        return f"Switched to tab {index}: {page.url}"
    except ToolError:
        raise
    except Exception as e:
        _fail(f"Failed to switch to tab {index}", e)


@mcp.tool()
async def set_viewport(width: int, height: int) -> str:
    """Force a viewport size, e.g. to test a mobile breakpoint.

    The browser otherwise opens maximized and the page fills the whole window.
    Once set, the viewport stays fixed for the life of the page.
    """
    try:
        await open_browser()
        await page.set_viewport_size({"width": width, "height": height})
        return f"Viewport set to {width}x{height}."
    except Exception as e:
        _fail(f"Failed to set viewport to {width}x{height}", e)


@mcp.tool()
async def snapshot_dom(limit: int = 40, frame: str = "") -> str:
    """List the interactive elements currently visible on the page.

    Reports each element's real identifying attributes - including aria-label,
    role and href - so a selector can be chosen from what is actually on the
    page instead of guessed. Also lists any iframes, whose contents are NOT
    included here: pass that iframe's selector as `frame` to look inside it.
    """
    try:
        await open_browser()
        js = """() => {
            const vis = el => {
                const r = el.getBoundingClientRect();
                return r.width > 0 && r.height > 0 &&
                       getComputedStyle(el).visibility !== 'hidden';
            };
            const els = [];
            document.querySelectorAll(
                'input, button, a, select, textarea, [role=button], [role=link],'
                + ' [role=menuitem], [role=tab], [onclick], [tabindex]'
            ).forEach(el => {
                if (!vis(el)) return;
                els.push({
                    tag:   el.tagName.toLowerCase(),
                    id:    el.id || '',
                    name:  el.getAttribute('name') || '',
                    type:  el.getAttribute('type') || '',
                    role:  el.getAttribute('role') || '',
                    aria:  el.getAttribute('aria-label') || '',
                    href:  el.getAttribute('href') || '',
                    ph:    el.getAttribute('placeholder') || '',
                    title: el.getAttribute('title') || '',
                    tid:   el.getAttribute('data-testid') || el.getAttribute('data-test') || '',
                    cls:   (typeof el.className === 'string' ? el.className : '').slice(0, 40),
                    dis:   el.disabled === true,
                    text:  (el.innerText || el.value || '').trim().slice(0, 45),
                });
            });
            const frames = [...document.querySelectorAll('iframe')].filter(vis).map(f => ({
                id: f.id || '', name: f.getAttribute('name') || '',
                src: (f.getAttribute('src') || '').slice(0, 80),
            }));
            return {els, frames, total: els.length};
        }"""
        if frame:
            handle = await page.query_selector(frame)
            if handle is None:
                raise ToolError(f"No iframe matches selector {frame}.")
            target = await handle.content_frame()
            if target is None:
                raise ToolError(f"{frame} is not an iframe, or its document is unavailable.")
            data = await _retry_nav(lambda: target.evaluate(js))
            where = f"iframe {frame}"
        else:
            data = await _retry_nav(lambda: page.evaluate(js))
            where = page.url

        if not data["els"] and not frame:
            # An empty result is usually a timing artefact, not an empty page:
            # a client-rendered page reaches readyState "complete" with a shell
            # whose controls are still display:none, and hydrates a second or
            # two later. Waiting on load() is no help - it has already fired -
            # so poll briefly before believing the page is really empty.
            try:
                await page.wait_for_load_state("load", timeout=8000)
            except Exception:
                pass
            for delay in (0.5, 1.0, 1.5, 2.0):
                await asyncio.sleep(delay)
                data = await _retry_nav(lambda: page.evaluate(js))
                if data["els"]:
                    break

        if not data["els"]:
            ready = await _retry_nav(lambda: page.evaluate("() => document.readyState"))
            return (f"No visible interactive elements found on {where} "
                    f"(document.readyState = {ready}).")

        lines = [f"Interactive elements on {where} ({data['total']} found):"]
        for el in data["els"][:limit]:
            parts = [f"<{el['tag']}"]
            for attr, key in (("id", "id"), ("name", "name"), ("type", "type"),
                              ("role", "role"), ("aria-label", "aria"), ("href", "href"),
                              ("placeholder", "ph"), ("title", "title"),
                              ("data-testid", "tid"), ("class", "cls")):
                if el[key]:
                    parts.append(f' {attr}="{el[key]}"')
            if el["dis"]:
                parts.append(" disabled")
            parts.append(">")
            if el["text"]:
                parts.append(f'  {el["text"]}')
            lines.append("  " + "".join(parts))
        if data["total"] > limit:
            lines.append(f"  ... {data['total'] - limit} more (raise limit to see them)")
        if data["frames"]:
            lines.append("")
            lines.append("iframes on this page (pass one as `frame` to inspect inside):")
            for f in data["frames"]:
                lines.append(f"  <iframe id=\"{f['id']}\" name=\"{f['name']}\" src=\"{f['src']}\">")
        return "\n".join(lines)
    except Exception as e:
        _fail("Failed to snapshot DOM", e)


@mcp.tool()
async def evaluate_script(script: str) -> str:
    """Evaluate a JavaScript expression in the page and return the result as JSON.

    Safe to call straight after a click that navigates - the call is retried
    once the new document is ready rather than failing on a destroyed context.
    """
    try:
        await open_browser()
        result = await _retry_nav(lambda: page.evaluate(script))
        try:
            return json.dumps(result, indent=2, default=str)
        except (TypeError, ValueError):
            return str(result)
    except Exception as e:
        _fail("Failed to evaluate script", e)


@mcp.tool()
async def take_screenshot(full_page: bool = False, png: bool = False,
                          quality: int = 60) -> Image:
    """Screenshot the current page as a real image.

    Defaults to JPEG, which on a photo-heavy page is roughly a seventh the size
    of the PNG. Set png=True only when you need exact pixels, e.g. for a visual
    diff - a full-page PNG of a rich page runs to hundreds of kilobytes.
    """
    try:
        await open_browser()
        if png:
            data = await page.screenshot(full_page=full_page)
            return Image(data=data, format="png")
        data = await page.screenshot(full_page=full_page, type="jpeg", quality=quality)
        return Image(data=data, format="jpeg")
    except Exception as e:
        _fail("Failed to take screenshot", e)


@mcp.tool()
async def save_session(path: str = "session.json") -> str:
    """Save cookies and localStorage to a file so a later run can skip logging in."""
    try:
        await open_browser()
        await context.storage_state(path=path)
        return (f"Session saved to {path}. Call load_session('{path}') at the start "
                f"of the next run to reuse it instead of logging in again.")
    except Exception as e:
        _fail(f"Failed to save session to {path}", e)


@mcp.tool()
async def load_session(path: str = "session.json") -> str:
    """Restore a session saved by save_session, then reopen the browser.

    Restarts the browser, so any page currently open is discarded.
    """
    global _storage_state_path
    try:
        await close_browser()
        _storage_state_path = path
        await open_browser()
        return f"Loaded session from {path}. Browser reopened with those cookies."
    except Exception as e:
        _storage_state_path = None
        _fail(f"Failed to load session from {path}", e)


@mcp.tool()
async def close_browser() -> str:
    """Close the browser and release Playwright.

    The next tool call starts a fresh browser, so this also resets cookies and
    session state mid-run.
    """
    global playwright_instance, browser, context, page
    try:
        if browser is not None:
            await browser.close()
        if playwright_instance is not None:
            await playwright_instance.stop()
    except Exception as e:
        # Keep the handles so a retry can still close them - dropping the refs
        # here would orphan the Chromium process with nothing left to kill it.
        _fail("Failed to close browser", e)
    playwright_instance = browser = context = page = None
    return "Browser closed."


if __name__ == "__main__":
    try:
        mcp.run()
    finally:
        # The browser was created on the event loop that mcp.run() owned, and
        # that loop is gone by the time we reach here - awaiting those objects
        # from a new loop fails. Chromium exits with this process anyway; call
        # the close_browser tool for a clean shutdown while the server is live.
        print("Playwright MCP server has been shut down.", file=sys.stderr)
