<script setup lang="ts">
import {
  message,
  Upload,
  UploadDragger,
  type UploadProps
} from "ant-design-vue"
import { FilePlus2 } from "@lucide/vue"

const emit = defineEmits<{
  "files-selected": [files: File[]]
}>()

const acceptedExtensions = new Set([
  "pdf",
  "doc",
  "docx",
  "txt",
  "md",
  "markdown",
  "csv",
  "xls",
  "xlsx",
  "ppt",
  "pptx",
  "png",
  "jpg",
  "jpeg",
  "webp"
])

/** 接收本地文件，但阻止组件发起尚未接通的上传请求。 */
const selectLocalFile: UploadProps["beforeUpload"] = (file) => {
  const extension = file.name.split(".").pop()?.toLocaleLowerCase() ?? ""
  if (!acceptedExtensions.has(extension)) {
    void message.warning(`${file.name} is not a supported source type.`)
    return Upload.LIST_IGNORE
  }

  emit("files-selected", [file as File])
  return Upload.LIST_IGNORE
}
</script>

<template>
  <UploadDragger
    class="knowledge-file-add"
    name="knowledge-file"
    accept=".pdf,.doc,.docx,.txt,.md,.markdown,.csv,.xls,.xlsx,.ppt,.pptx,.png,.jpg,.jpeg,.webp"
    multiple
    :before-upload="selectLocalFile"
    :show-upload-list="false"
  >
    <div class="knowledge-file-add-content">
      <span class="knowledge-file-add-icon" aria-hidden="true">
        <FilePlus2 :size="18" :stroke-width="1.8" />
      </span>
      <span class="knowledge-file-add-copy">
        <strong>Add files</strong>
      </span>
    </div>
  </UploadDragger>
</template>

<style scoped>
@reference "../styles/index.css";

.knowledge-file-add {
  @apply block;
}

.knowledge-file-add :deep(.ant-upload-drag) {
  min-height: 5rem;
  border: 1px dashed var(--color-border-control);
  border-radius: var(--radius-md);
  background: var(--color-surface-muted);
  transition:
    border-color 140ms ease,
    background-color 140ms ease;
}

.knowledge-file-add :deep(.ant-upload-drag:hover),
.knowledge-file-add :deep(.ant-upload-drag-hover) {
  border-color: var(--color-border-focus);
  background: var(--color-surface-emphasis);
}

.knowledge-file-add :deep(.ant-upload-btn) {
  padding: 0.75rem !important;
}

.knowledge-file-add-content {
  @apply flex items-center text-left;

  gap: 0.65rem;
}

.knowledge-file-add-icon {
  @apply grid shrink-0 place-items-center;

  width: 2.15rem;
  height: 2.15rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-text);
  background: var(--color-surface);
}

.knowledge-file-add-copy {
  @apply min-w-0;
}

.knowledge-file-add-copy strong {
  @apply font-semibold;

  color: var(--color-text);
  font-size: 0.9rem;
  letter-spacing: -0.01em;
}
</style>
