import { ImageResponse } from "workers-og";
import ptSerif from "./fonts/PTSerif-Regular.ttf";
import { escapeHtml, type CardModel } from "./shared/meta";

const FONT = ptSerif as unknown as ArrayBuffer;

export function renderCard(m: CardModel): Response {
  const e = escapeHtml;
  const modern = m.modern
    ? `<div style="font-size:34px;font-style:italic;color:#6f6a5c;margin-top:20px;display:flex;">${e(m.modern)}</div>`
    : "";
  // verba willow palette: linen bg #f4f1e8, willow rule #5e7355, ink #232520, muted #6f6a5c
  const html = `<div style="display:flex;flex-direction:column;width:1200px;height:630px;background:#f4f1e8;padding:72px;font-family:'PT Serif';">
  <div style="display:flex;width:96px;height:8px;background:#5e7355;"></div>
  <div style="display:flex;flex-direction:column;flex:1;justify-content:center;">
    <div style="font-size:62px;color:#232520;line-height:1.18;display:flex;">${e(m.text)}</div>
    ${modern}
  </div>
  <div style="display:flex;font-size:26px;color:#6f6a5c;">${e(m.footer)}</div>
</div>`;
  return new ImageResponse(html, {
    width: 1200,
    height: 630,
    fonts: [{ name: "PT Serif", data: FONT, weight: 400, style: "normal" }],
  });
}
