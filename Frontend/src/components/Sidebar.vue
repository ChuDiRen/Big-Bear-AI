<template>
  <aside class="sidebar">
    <div class="logo-area">
      <i class="ph-fill ph-robot logo-icon"></i>
      <span>大熊AI</span>
    </div>
    <nav class="nav-menu">
      <router-link to="/" class="nav-item" active-class="active">
        <i class="ph ph-house"></i>
        <span>Home</span>
      </router-link>
      <router-link to="/rules" class="nav-item" active-class="active">
        <i class="ph ph-scroll"></i>
        <span>Rules</span>
      </router-link>
      <router-link to="/agents" class="nav-item" active-class="active">
        <i class="ph ph-robot"></i>
        <span>智能体</span>
      </router-link>
      <router-link to="/prompt" class="nav-item" active-class="active">
        <i class="ph ph-magic-wand"></i>
        <span>Prompt</span>
      </router-link>
      <router-link to="/mcp" class="nav-item" active-class="active">
        <i class="ph ph-plugs-connected"></i>
        <span>MCP</span>
      </router-link>
      <router-link to="/knowledge" class="nav-item" active-class="active">
        <i class="ph ph-books"></i>
        <span>知识库</span>
      </router-link>
      <router-link to="/plugins" class="nav-item" active-class="active">
        <i class="ph ph-puzzle-piece"></i>
        <span>插件</span>
      </router-link>
    </nav>
    <div class="account-menu">
      <span>{{ authSession?.user?.display_name || authSession?.user?.username }}</span>
      <button type="button" @click="signOut">
        <i class="ph ph-sign-out" aria-hidden="true"></i>
        退出登录
      </button>
    </div>
  </aside>
</template>

<script setup>
import { useRouter } from 'vue-router'

import { authSession, logout } from '../api/auth.js'


const router = useRouter()

function signOut() {
  logout()
  router.replace('/auth')
}
</script>

<style scoped>
/* Sidebar styles are in layout.css */
</style>
