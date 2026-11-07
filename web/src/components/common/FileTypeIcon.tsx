import pdfIcon from "@/assets/material-icons/pdf.svg"
import wordIcon from "@/assets/material-icons/word.svg"
import tableIcon from "@/assets/material-icons/table.svg"
import powerpointIcon from "@/assets/material-icons/powerpoint.svg"
import imageIcon from "@/assets/material-icons/image.svg"
import zipIcon from "@/assets/material-icons/zip.svg"
import documentIcon from "@/assets/material-icons/document.svg"
import pythonIcon from "@/assets/material-icons/python.svg"
import javascriptIcon from "@/assets/material-icons/javascript.svg"
import typescriptIcon from "@/assets/material-icons/typescript.svg"
import jsonIcon from "@/assets/material-icons/json.svg"
import markdownIcon from "@/assets/material-icons/markdown.svg"
import audioIcon from "@/assets/material-icons/audio.svg"
import videoIcon from "@/assets/material-icons/video.svg"
import htmlIcon from "@/assets/material-icons/html.svg"
import cssIcon from "@/assets/material-icons/css.svg"
import xmlIcon from "@/assets/material-icons/xml.svg"
import yamlIcon from "@/assets/material-icons/yaml.svg"
import { cn } from "@/lib/utils"

const iconsByExtension: Record<string, string> = {
  pdf: pdfIcon,
  doc: wordIcon,
  docx: wordIcon,
  rtf: wordIcon,
  odt: wordIcon,
  xls: tableIcon,
  xlsx: tableIcon,
  xlsm: tableIcon,
  csv: tableIcon,
  tsv: tableIcon,
  ods: tableIcon,
  ppt: powerpointIcon,
  pptx: powerpointIcon,
  odp: powerpointIcon,
  png: imageIcon,
  jpg: imageIcon,
  jpeg: imageIcon,
  gif: imageIcon,
  webp: imageIcon,
  svg: imageIcon,
  bmp: imageIcon,
  ico: imageIcon,
  tif: imageIcon,
  tiff: imageIcon,
  avif: imageIcon,
  zip: zipIcon,
  rar: zipIcon,
  "7z": zipIcon,
  tar: zipIcon,
  gz: zipIcon,
  bz2: zipIcon,
  xz: zipIcon,
  py: pythonIcon,
  pyi: pythonIcon,
  ipynb: pythonIcon,
  js: javascriptIcon,
  jsx: javascriptIcon,
  mjs: javascriptIcon,
  cjs: javascriptIcon,
  ts: typescriptIcon,
  tsx: typescriptIcon,
  mts: typescriptIcon,
  cts: typescriptIcon,
  json: jsonIcon,
  jsonl: jsonIcon,
  jsonc: jsonIcon,
  md: markdownIcon,
  mdx: markdownIcon,
  markdown: markdownIcon,
  mp3: audioIcon,
  wav: audioIcon,
  ogg: audioIcon,
  flac: audioIcon,
  m4a: audioIcon,
  aac: audioIcon,
  mp4: videoIcon,
  webm: videoIcon,
  mov: videoIcon,
  avi: videoIcon,
  mkv: videoIcon,
  html: htmlIcon,
  htm: htmlIcon,
  css: cssIcon,
  scss: cssIcon,
  sass: cssIcon,
  less: cssIcon,
  xml: xmlIcon,
  yaml: yamlIcon,
  yml: yamlIcon,
}

export function FileTypeIcon({ name, className }: { name: string; className?: string }) {
  const extension = name.includes(".") ? name.split(".").pop()!.toLowerCase() : ""
  return <img src={iconsByExtension[extension] ?? documentIcon} alt="" className={cn("size-5 shrink-0", className)} />
}
