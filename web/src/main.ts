import { createApp } from "vue"

import "@fontsource-variable/noto-sans-sc"

import App from "@/App.vue"
import router from "@/router"
import "@/styles/index.css"

createApp(App).use(router).mount("#app")
