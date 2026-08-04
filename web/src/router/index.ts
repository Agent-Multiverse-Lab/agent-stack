import { createRouter, createWebHistory } from "vue-router"

import AuthenticationView from "@/views/AuthenticationView.vue"
import ChatView from "@/views/ChatView.vue"
import KnowledgeView from "@/views/KnowledgeView.vue"
import NavigationView from "@/views/NavigationView.vue"
import UnavailableFeatureView from "@/views/UnavailableFeatureView.vue"

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
          path: ":featureId(library|agent|image|static|sandbox)",
          name: "feature",
          component: UnavailableFeatureView,
          props: true
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
