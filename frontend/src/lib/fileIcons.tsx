import { Folder, Film, Music, Archive, FileText, File } from "lucide-react";

export function getFileCategory(name: string, mimeType: string): "folder" | "video" | "audio" | "archive" | "document" | "generic" {
  if (mimeType === "application/vnd.google-apps.folder") return "folder";

  const lowerName = name.toLowerCase();
  const lowerMime = mimeType.toLowerCase();

  if (
    lowerMime.startsWith("video/") ||
    lowerName.endsWith(".mp4") ||
    lowerName.endsWith(".mkv") ||
    lowerName.endsWith(".webm") ||
    lowerName.endsWith(".avi") ||
    lowerName.endsWith(".mov")
  ) {
    return "video";
  }

  if (
    lowerMime.startsWith("audio/") ||
    lowerName.endsWith(".mp3") ||
    lowerName.endsWith(".flac") ||
    lowerName.endsWith(".wav") ||
    lowerName.endsWith(".m4a") ||
    lowerName.endsWith(".aac")
  ) {
    return "audio";
  }

  if (
    lowerMime.includes("zip") ||
    lowerMime.includes("tar") ||
    lowerMime.includes("compressed") ||
    lowerName.endsWith(".zip") ||
    lowerName.endsWith(".tar") ||
    lowerName.endsWith(".tar.gz") ||
    lowerName.endsWith(".iso") ||
    lowerName.endsWith(".rar") ||
    lowerName.endsWith(".7z")
  ) {
    return "archive";
  }

  if (
    lowerMime.startsWith("text/") ||
    lowerMime.includes("pdf") ||
    lowerName.endsWith(".pdf") ||
    lowerName.endsWith(".txt") ||
    lowerName.endsWith(".md") ||
    lowerName.endsWith(".nfo")
  ) {
    return "document";
  }

  return "generic";
}

export function isMediaFile(name: string, mimeType: string): boolean {
  const category = getFileCategory(name, mimeType);
  return category === "video" || category === "audio";
}

export function renderFileIcon(category: ReturnType<typeof getFileCategory>, className = "w-5 h-5") {
  switch (category) {
    case "folder":
      return <Folder className={`${className} text-accent-1 fill-accent-1/20`} />;
    case "video":
      return <Film className={`${className} text-accent-2`} />;
    case "audio":
      return <Music className={`${className} text-success`} />;
    case "archive":
      return <Archive className={`${className} text-warning`} />;
    case "document":
      return <FileText className={`${className} text-text`} />;
    case "generic":
    default:
      return <File className={`${className} text-text-muted`} />;
  }
}
