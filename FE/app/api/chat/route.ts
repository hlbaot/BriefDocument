import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

async function readBackendError(response: Response) {
  try {
    const data = (await response.json()) as { detail?: string; error?: string };
    return data.detail || data.error || "Backend khong tra ve chi tiet loi.";
  } catch {
    const text = await response.text();
    return text || "Backend khong tra ve chi tiet loi.";
  }
}

export async function POST(request: NextRequest) {
  try {
    const contentType = request.headers.get("content-type") || "";

    if (contentType.includes("multipart/form-data")) {
      const formData = await request.formData();
      const response = await fetch(`${BACKEND_URL}/summarize/file`, {
        method: "POST",
        body: formData
      });

      if (!response.ok) {
        return NextResponse.json(
          { error: await readBackendError(response) },
          { status: response.status }
        );
      }

      const data = (await response.json()) as { summary?: string };
      return NextResponse.json({ reply: data.summary || "Khong co phan hoi tu AI." });
    }

    const body = (await request.json()) as {
      mode?: string;
      text?: string;
      link?: string;
    };

    const endpoint =
      body.mode === "link" ? "/summarize/link" : "/summarize/text";

    const payload =
      body.mode === "link"
        ? { url: body.link }
        : { text: body.text, sourceLabel: "Text nguoi dung" };

    const response = await fetch(`${BACKEND_URL}${endpoint}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      return NextResponse.json(
        { error: await readBackendError(response) },
        { status: response.status }
      );
    }

    const data = (await response.json()) as { summary?: string };
    return NextResponse.json({ reply: data.summary || "Khong co phan hoi tu AI." });
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Khong the ket noi toi backend Python.";

    return NextResponse.json({ error: message }, { status: 500 });
  }
}
