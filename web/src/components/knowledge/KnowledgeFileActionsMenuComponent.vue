<script setup lang="ts">
import { h } from "vue"
import {
  Button as AButton,
  Dropdown as ADropdown,
  Menu as AMenu,
  Modal,
  type MenuProps
} from "ant-design-vue"
import { MoreHorizontal, TriangleAlert } from "@lucide/vue"

import type { KnowledgeFileItem } from "@/types/knowledge"

const props = defineProps<{
  file: KnowledgeFileItem
}>()

const emit = defineEmits<{
  remove: [fileId: string]
}>()

const menuItems: MenuProps["items"] = [
  { key: "open", label: "Open file" },
  { key: "download", label: "Download a copy" },
  { key: "rename", label: "Rename", disabled: true },
  { type: "divider" },
  { key: "parse", label: "Parse file", disabled: true },
  { key: "index", label: "Build index", disabled: true },
  { type: "divider" },
  { key: "remove", label: "Remove from list", danger: true }
]

/** 在新的浏览器标签中打开文件。 */
const openFile = () => {
  const objectUrl = URL.createObjectURL(props.file.source)
  window.open(objectUrl, "_blank", "noopener,noreferrer")
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000)
}

/** 通过浏览器下载当前文件的副本。 */
const downloadFile = () => {
  const objectUrl = URL.createObjectURL(props.file.source)
  const link = document.createElement("a")
  link.href = objectUrl
  link.download = props.file.name
  link.click()
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0)
}

/** 在列表移除文件前显示明确确认。 */
const confirmRemoval = () => {
  Modal.confirm({
    title: "Remove this file?",
    content: `${props.file.name} will be removed from this list.`,
    icon: h(TriangleAlert, {
      size: 20,
      strokeWidth: 1.8,
      color: "var(--color-danger)",
      "aria-hidden": "true"
    }),
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
    openFile()
    return
  }

  if (key === "download") {
    downloadFile()
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
      class="knowledge-file-menu-trigger grid! h-11! w-11! min-w-11! shrink-0 place-items-center text-slate! hover:bg-graphite/8! hover:text-graphite! focus-visible:bg-graphite/8! focus-visible:text-graphite!"
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
