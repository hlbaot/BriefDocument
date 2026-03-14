"use client";

import { ChangeEvent, FormEvent, useState } from "react";

type InputMode = "text" | "link" | "file";

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

const starterMessages: Message[] = [
  {
    id: "assistant-welcome",
    role: "assistant",
    content:
      "Chon mot kieu dau vao o phia tren: dan text, gui link, hoac tai file len. Toi se tra ket qua tom tat theo dang chat."
  }
];

const modeLabels: Record<InputMode, string> = {
  text: "Text",
  link: "Link",
  file: "File"
};

const modeDescriptions: Record<InputMode, string> = {
  text: "Dan noi dung tho, note hop, bai viet hoac transcript.",
  link: "Gui URL de backend scrape noi dung roi tom tat.",
  file: "Tai len PDF, DOCX, TXT hoac Markdown tu may cua ban."
};

function createAssistantMessage(content: string): Message {
  return {
    id: `assistant-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    role: "assistant",
    content
  };
}

export default function HomePage() {
  const [mode, setMode] = useState<InputMode>("text");
  const [messages, setMessages] = useState<Message[]>(starterMessages);
  const [textInput, setTextInput] = useState("");
  const [linkInput, setLinkInput] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  function appendUserMessage(content: string) {
    const userMessage: Message = {
      id: `user-${Date.now()}-${Math.random().toString(16).slice(2)}`,
      role: "user",
      content
    };

    setMessages((current) => [...current, userMessage]);
  }

  async function sendJson(payload: Record<string, string>) {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });

    const data = (await response.json()) as { reply?: string; error?: string };
    if (!response.ok) {
      throw new Error(data.error || "Khong the xu ly yeu cau.");
    }

    return data.reply || "Khong co phan hoi tu AI.";
  }

  async function sendFile(file: File) {
    const formData = new FormData();
    formData.append("mode", "file");
    formData.append("sourceLabel", "File nguoi dung");
    formData.append("file", file);

    const response = await fetch("/api/chat", {
      method: "POST",
      body: formData
    });

    const data = (await response.json()) as { reply?: string; error?: string };
    if (!response.ok) {
      throw new Error(data.error || "Khong the xu ly file.");
    }

    return data.reply || "Khong co phan hoi tu AI.";
  }

  async function handleTextSubmit() {
    const trimmed = textInput.trim();
    if (!trimmed) {
      return;
    }

    appendUserMessage(trimmed);
    setTextInput("");

    const reply = await sendJson({
      mode: "text",
      text: trimmed
    });

    setMessages((current) => [...current, createAssistantMessage(reply)]);
  }

  async function handleLinkSubmit() {
    const trimmed = linkInput.trim();
    if (!trimmed) {
      return;
    }

    appendUserMessage(`Tom tat tu link:\n${trimmed}`);
    setLinkInput("");

    const reply = await sendJson({
      mode: "link",
      link: trimmed
    });

    setMessages((current) => [...current, createAssistantMessage(reply)]);
  }

  async function handleFileSubmit() {
    if (!selectedFile) {
      throw new Error("Ban chua chon file.");
    }

    appendUserMessage(
      `Tom tat tu file:\n${selectedFile.name} (${Math.ceil(selectedFile.size / 1024)} KB)`
    );
    const file = selectedFile;
    setSelectedFile(null);
    const reply = await sendFile(file);

    setMessages((current) => [...current, createAssistantMessage(reply)]);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isLoading) {
      return;
    }

    setIsLoading(true);

    try {
      if (mode === "text") {
        await handleTextSubmit();
      } else if (mode === "link") {
        await handleLinkSubmit();
      } else {
        await handleFileSubmit();
      }
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Co loi khong xac dinh.";

      setMessages((current) => [
        ...current,
        createAssistantMessage(`Khong the tao tom tat.\n\n${message}`)
      ]);
    } finally {
      setIsLoading(false);
    }
  }

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    const nextFile = event.target.files?.[0] || null;
    setSelectedFile(nextFile);
  }

  return (
    <main className="shell">
      <section className="hero">
        <p className="eyebrow">BriefDocument AI</p>
        <h1>Tom tat van ban</h1>
        <p className="subtitle">
          Nguoi dung co the dan text, gui link bai viet, hoac tai file tu may.
          Phia duoi van giu trai nghiem tra loi theo dang chat de de doc va de
          theo doi lich su tom tat.
        </p>
      </section>

      <section className="modeStrip" aria-label="Che do nhap lieu">
        {(["text", "link", "file"] as InputMode[]).map((item) => (
          <button
            key={item}
            type="button"
            className={`modeTab ${mode === item ? "active" : ""}`}
            onClick={() => setMode(item)}
          >
            <strong>{modeLabels[item]}</strong>
            <span>{modeDescriptions[item]}</span>
          </button>
        ))}
      </section>

      <section className="chatCard">
        <div className="chatHeader">
          <div>
            <strong>Assistant</strong>
            <p>{modeDescriptions[mode]}</p>
          </div>
          <span className="status">{isLoading ? "Dang xu ly" : "San sang"}</span>
        </div>

        <div className="messages">
          {messages.map((message) => (
            <article
              key={message.id}
              className={`bubble ${message.role === "user" ? "user" : "assistant"}`}
            >
              <span className="roleLabel">
                {message.role === "user" ? "Ban" : "AI"}
              </span>
              <pre>{message.content}</pre>
            </article>
          ))}

          {isLoading ? (
            <article className="bubble assistant">
              <span className="roleLabel">AI</span>
              <pre>Dang doc dau vao va tao tom tat...</pre>
            </article>
          ) : null}
        </div>

        <form className="composer" onSubmit={handleSubmit}>
          {mode === "text" ? (
            <textarea
              value={textInput}
              onChange={(event) => setTextInput(event.target.value)}
              placeholder="Dan van ban can tom tat..."
              rows={7}
            />
          ) : null}

          {mode === "link" ? (
            <div className="inputPanel">
              <label className="inputLabel" htmlFor="link-input">
                Link bai viet hoac trang web
              </label>
              <input
                id="link-input"
                className="textField"
                type="url"
                value={linkInput}
                onChange={(event) => setLinkInput(event.target.value)}
                placeholder="https://example.com/bai-viet"
              />
              <p className="helperText">
                Dau vao nay se hop voi pipeline Playwright + BeautifulSoup o
                backend Python cua ban.
              </p>
            </div>
          ) : null}

          {mode === "file" ? (
            <div className="inputPanel">
              <label className="uploadBox" htmlFor="file-input">
                <span className="uploadTitle">Chon file de tom tat</span>
                <span className="uploadHint">
                  Ho tro PDF, DOCX, TXT, Markdown, JSON va CSV. Viec doc noi
                  dung file se duoc backend Python xu ly.
                </span>
                <span className="uploadMeta">
                  {selectedFile
                    ? `${selectedFile.name} - ${Math.ceil(selectedFile.size / 1024)} KB`
                    : "Chua chon file"}
                </span>
              </label>
              <input
                id="file-input"
                className="hiddenInput"
                type="file"
                accept=".pdf,.docx,.txt,.md,.markdown,.json,.csv"
                onChange={onFileChange}
              />
            </div>
          ) : null}

          <div className="composerActions">
            <p>
              Mode hien tai: <strong>{modeLabels[mode]}</strong>
            </p>
            <button
              type="submit"
              disabled={
                isLoading ||
                (mode === "text" && !textInput.trim()) ||
                (mode === "link" && !linkInput.trim()) ||
                (mode === "file" && !selectedFile)
              }
            >
              {isLoading ? "Dang gui..." : "Gui"}
            </button>
          </div>
        </form>
      </section>
    </main>
  );
}
