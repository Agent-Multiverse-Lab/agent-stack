<script setup lang="ts">
import { LogOut, Settings, UserRound } from "@lucide/vue"
import {
  Dropdown as ADropdown,
  Menu as AMenu,
  MenuItem as AMenuItem
} from "ant-design-vue"

import UserAvatarComponent from "@/components/UserAvatarComponent.vue"

defineProps<{
  username: string
  collapsed: boolean
}>()

const emit = defineEmits<{
  profile: []
  settings: []
  logout: []
}>()
</script>

<template>
  <ADropdown placement="topLeft" trigger="click">
    <button
      class="grid min-h-10 w-full items-center rounded-sm bg-transparent text-left text-sm text-slate transition-colors hover:bg-graphite/8 hover:text-graphite"
      :class="collapsed
        ? 'place-items-center px-0'
        : '[grid-template-columns:28px_minmax(0,1fr)] gap-2 px-2'"
      type="button"
      :aria-label="`Open ${username} account menu`"
      aria-haspopup="menu"
    >
      <UserAvatarComponent :label="username" />
      <span v-if="!collapsed" class="truncate font-medium text-graphite">
        {{ username }}
      </span>
    </button>

    <template #overlay>
      <AMenu class="min-w-40">
        <AMenuItem key="profile" @click="emit('profile')">
          <div class="flex items-center gap-2 text-xs">
            <UserRound :size="14" :stroke-width="1.8" aria-hidden="true" />
            <span>Profile</span>
          </div>
        </AMenuItem>
        <AMenuItem key="settings" @click="emit('settings')">
          <div class="flex items-center gap-2 text-xs">
            <Settings :size="14" :stroke-width="1.8" aria-hidden="true" />
            <span>Settings</span>
          </div>
        </AMenuItem>
        <AMenuItem key="logout" danger @click="emit('logout')">
          <div class="flex items-center gap-2 text-xs">
            <LogOut :size="14" :stroke-width="1.8" aria-hidden="true" />
            <span>Log out</span>
          </div>
        </AMenuItem>
      </AMenu>
    </template>
  </ADropdown>
</template>
