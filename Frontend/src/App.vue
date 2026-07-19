<template>
  <router-view v-slot="{ Component, route }">
    <div v-if="route.meta.public" class="auth-shell">
      <component :is="Component" />
    </div>
    <div v-else class="app-container">
      <Sidebar />
      <component :is="Component" />
    </div>
  </router-view>
</template>

<script setup>
import Sidebar from './components/Sidebar.vue';
</script>

<style>
/* Global styles are imported in main.js */
</style>
