import { createRouter, createWebHistory } from "vue-router"

import AuthenticationView from "@/views/AuthenticationView.vue"
import ChatView from "@/views/ChatView.vue"
import KnowledgeView from "@/views/KnowledgeView.vue"
import NavigationView from "@/views/NavigationView.vue"
import AgentView from "@/views/AgentView.vue"
import LibraryView from "@/views/LibraryView.vue"
import SandboxView from "@/views/SandboxView.vue"
import StaticView from "@/views/StaticView.vue"

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      component: NavigationView,
      children: [
        {
          path: "",
          name: "chat",
          component: ChatView,
          meta: { title: "Chat" }
        },
        {
          path: "c/:conversationId",
          name: "conversation",
          component: ChatView,
          props: (route) => ({
            conversationId:
              typeof route.params.conversationId === "string"
                ? route.params.conversationId
                : undefined
          }),
          meta: { title: "Chat" }
        },
        {
          path: "library",
          name: "library",
          component: LibraryView,
          meta: { title: "Library" }
        },
        {
          path: "agent",
          name: "agent",
          component: AgentView,
          meta: { title: "Agent" }
        },
        {
          path: "static",
          name: "static",
          component: StaticView,
          meta: { title: "Static" }
        },
        {
          path: "sandbox",
          name: "sandbox",
          component: SandboxView,
          meta: { title: "Sandbox" }
        }
      ]
    },
    {
      path: "/knowledge",
      name: "knowledge",
      component: KnowledgeView,
      meta: { title: "Knowledge" }
    },
    {
      path: "/login",
      name: "login",
      component: AuthenticationView,
      props: { mode: "login" }
    },
    {
      path: "/register",
      name: "register",
      component: AuthenticationView,
      props: { mode: "register" }
    },
    {
      path: "/:pathMatch(.*)*",
      redirect: "/"
    }
  ],
  scrollBehavior: () => ({ top: 0 })
})

export default router
