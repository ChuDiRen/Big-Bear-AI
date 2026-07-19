<template>
  <main class="auth-page">
    <section class="auth-card" aria-labelledby="auth-title">
      <div class="auth-brand">
        <i class="ph-fill ph-robot" aria-hidden="true"></i>
        <span>大熊AI</span>
      </div>
      <p class="auth-kicker">测试工作台</p>
      <h1 id="auth-title">{{ mode === 'login' ? '欢迎回来' : '创建账户' }}</h1>
      <p class="auth-description">
        {{ mode === 'login' ? '登录后继续访问你的智能体和测试资源。' : '创建账户后即可开始使用测试工作台。' }}
      </p>

      <form class="auth-form" @submit.prevent="submit">
        <label v-if="mode === 'register'">
          <span>邮箱</span>
          <input v-model.trim="form.email" type="email" autocomplete="email" required>
        </label>
        <label>
          <span>用户名</span>
          <input v-model.trim="form.username" type="text" autocomplete="username" minlength="3" maxlength="50" required>
        </label>
        <label v-if="mode === 'register'">
          <span>显示名称</span>
          <input v-model.trim="form.displayName" type="text" maxlength="100" placeholder="可选">
        </label>
        <label>
          <span>密码</span>
          <input v-model="form.password" type="password" autocomplete="current-password" minlength="8" required>
        </label>
        <p v-if="error" class="auth-error" role="alert">{{ error }}</p>
        <button class="auth-submit" type="submit" :disabled="submitting">
          {{ submitting ? '处理中...' : mode === 'login' ? '登录' : '注册并登录' }}
        </button>
      </form>

      <button class="auth-switch" type="button" @click="switchMode">
        {{ mode === 'login' ? '没有账户？创建一个' : '已有账户？返回登录' }}
      </button>
    </section>
  </main>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { login, register } from '../api/auth.js'


const router = useRouter()
const mode = ref('login')
const submitting = ref(false)
const error = ref('')
const form = reactive({ username: '', email: '', password: '', displayName: '' })


async function submit() {
  submitting.value = true
  error.value = ''
  try {
    if (mode.value === 'login') {
      await login({ username: form.username, password: form.password })
    } else {
      await register({
        username: form.username,
        email: form.email,
        password: form.password,
        display_name: form.displayName || null,
      })
    }
    await router.replace(router.currentRoute.value.query.redirect || '/')
  } catch (reason) {
    error.value = reason.message
  } finally {
    submitting.value = false
  }
}


function switchMode() {
  mode.value = mode.value === 'login' ? 'register' : 'login'
  error.value = ''
}
</script>

<style scoped>
.auth-page { align-items: center; background: linear-gradient(135deg, #eaf3ff, #f8fafc); display: flex; justify-content: center; min-height: 100vh; padding: 24px; }
.auth-card { background: #fff; border: 1px solid var(--border-color); border-radius: 20px; box-shadow: var(--shadow-lg); max-width: 420px; padding: 36px; width: 100%; }
.auth-brand { align-items: center; color: var(--primary-color); display: flex; font-size: 20px; font-weight: 700; gap: 10px; }
.auth-brand i { font-size: 28px; }
.auth-kicker { color: var(--text-tertiary); font-size: 14px; margin-top: 28px; }
h1 { font-size: 28px; margin-top: 4px; }
.auth-description { color: var(--text-secondary); margin-top: 8px; }
.auth-form { display: grid; gap: 16px; margin-top: 28px; }
.auth-form label { display: grid; font-size: 14px; font-weight: 600; gap: 6px; }
.auth-form input { border: 1px solid var(--border-color); border-radius: 8px; font-size: 15px; padding: 11px 12px; }
.auth-form input:focus { border-color: var(--primary-color); box-shadow: 0 0 0 3px #dbeafe; }
.auth-submit { background: var(--primary-color); border: 0; border-radius: 8px; color: #fff; cursor: pointer; font-weight: 700; padding: 12px; }
.auth-submit:disabled { cursor: wait; opacity: .65; }
.auth-switch { background: transparent; border: 0; color: var(--primary-color); cursor: pointer; display: block; margin: 20px auto 0; }
.auth-error { color: #b91c1c; font-size: 14px; }
</style>