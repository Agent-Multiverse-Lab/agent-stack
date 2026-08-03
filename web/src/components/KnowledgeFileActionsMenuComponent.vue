<script setup lang="ts">
import {
  Button as AButton,
  Dropdown as ADropdown,
  Menu as AMenu,
  Modal,
  type MenuProps
} from "ant-design-vue"
import { MoreHorizontal } from "@lucide/vue"

import type { KnowledgeFileItem } from "@/types/knowledge"

const props = defineProps<{
  file: KnowledgeFileItem
}>()

const emit = defineEmits<{
  remove: [fileId: string]
}>()

const menuItems: MenuProps["items"] = [
  { key: "open", label: "Open local file" },
  { key: "download", label: "Download a copy" },
  { key: "rename", label: "Rename", disabled: true },
  { type: "divider" },
  { key: "parse", label: "Parse file", disabled: true },
  { key: "index", label: "Build index", disabled: true },
  { type: "divider" },
  { key: "remove", label: "Remove from list", danger: true }
]

/** 在新的浏览器标签中打开本地文件。 */
const openLocalFile = () => {
  const objectUrl = URL.createObjectURL(props.file.source)
  window.open(objectUrl, "_blank", "noopener,noreferrer")
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000)
}

/** 通过浏览器下载当前本地文件的副本。 */
const downloadLocalFile = () => {
  const objectUrl = URL.createObjectURL(props.file.source)
  const link = document.createElement("a")
  link.href = objectUrl
  link.download = props.file.name
  link.click()
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0)
}

/** 在本地列表移除文件前显示明确确认。 */
const confirmRemoval = () => {
  Modal.confirm({
    title: "Remove this file?",
    content: `${props.file.name} will be removed from this local list.`,
    okText: "Remove",
    okType: "danger",
    cancelText: "Keep file",
    centered: true,
    onOk: () => emit("remove", props.file.id)
  })
}

/** 分发当前已具备真实行为的文件菜单操作。 */
const selectMenuItem: MenuProps["onClick"] = ({ key }) => {
  if (key === "open") {
    openLocalFile()
    return
  }

  if (key === "download") {
    downloadLocalFile()
    return
  }

  if (key === "remove") confirmRemoval()
}
</script>

<template>
  <ADropdown
    placement="bottomRight"
    :trigger="['click']"
  >
    <AButton
      class="knowledge-file-menu-trigger"
      type="text"
      shape="circle"
      aria-label="Open file actions"
      title="File actions"
      @click.stop
    >
      <MoreHorizontal :size="17" :stroke-width="1.9" aria-hidden="true" />
    </AButton>

    <template #overlay>
      <AMenu :items="menuItems" @click="selectMenuItem" />
    </template>
  </ADropdown>
</template>

<style scoped>
@reference "../styles/index.css";

.knowledge-file-menu-trigger {
  @apply grid shrink-0 place-items-center;

  width: 2.75rem;
  min-width: 2.75rem;
  height: 2.75rem;
  color: var(--color-text-muted);
}

.knowledge-file-menu-trigger:hover,
.knowledge-file-menu-trigger:focus-visible {
  color: var(--color-text);
  background: var(--color-surface-hover);
}
</style>
