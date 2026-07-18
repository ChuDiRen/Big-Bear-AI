<template>
  <main class="main-content">
    <header class="page-header">
      <h1 class="page-title">插件中心</h1>
      <p class="page-subtitle">安装并管理经过内置审核的工具插件</p>
      <div class="header-actions">
        <label class="search-bar">
          <i class="ph ph-magnifying-glass" aria-hidden="true"></i>
          <input v-model="search" type="search" placeholder="搜索插件...">
        </label>
        <div class="plugin-summary" aria-live="polite">
          {{ installedCount }} / {{ plugins.length }} 已安装
        </div>
      </div>
    </header>

    <p v-if="error" class="state-band error-state" role="alert">{{ error }}</p>
    <p v-if="loading" class="state-band" aria-busy="true">正在加载...</p>
    <p v-else-if="filteredPlugins.length === 0" class="state-band">没有匹配的插件</p>
    <div v-else class="card-grid">
      <UnifiedCard
        v-for="plugin in filteredPlugins"
        :key="plugin.id"
        data-plugin-card
        :item="plugin"
        :options="{
          badgeText: plugin.category,
          iconName: plugin.icon || 'puzzle-piece',
          statusText: pluginStatus(plugin),
        }"
        @select="openDetail"
      />
    </div>

    <AppModal :open="Boolean(selected)" :title="selected?.name ?? '插件详情'" @close="closeDetail">
      <template v-if="selected">
        <p class="plugin-description">{{ selected.description }}</p>
        <dl class="detail-list">
          <dt>分类</dt><dd>{{ selected.category }}</dd>
          <dt>状态</dt><dd>{{ pluginStatus(selected) }}</dd>
          <dt>配置 Schema</dt><dd><pre>{{ jsonText(selected.config_schema) }}</pre></dd>
        </dl>

        <label class="form-field">
          <span>配置 JSON</span>
          <textarea v-model="configuration" name="plugin-configuration" rows="5"></textarea>
        </label>

        <section v-if="selected.installed && selected.enabled" class="call-panel">
          <h3>试运行</h3>
          <label class="form-field">
            <span>输入 JSON</span>
            <textarea v-model="pluginInput" name="plugin-input" rows="5"></textarea>
          </label>
          <button data-call-plugin type="button" class="btn-secondary" @click="callPlugin">
            <i class="ph ph-play" aria-hidden="true"></i>
            调用插件
          </button>
          <pre v-if="pluginResult" class="plugin-result">{{ pluginResult }}</pre>
        </section>

        <p v-if="detailError" class="form-error" role="alert">{{ detailError }}</p>
        <div class="modal-actions">
          <button
            v-if="!selected.installed"
            data-install-plugin
            type="button"
            class="btn-primary"
            @click="install"
          >
            <i class="ph ph-download-simple" aria-hidden="true"></i>
            安装
          </button>
          <template v-else>
            <button data-configure-plugin type="button" class="btn-secondary" @click="configure">
              <i class="ph ph-sliders-horizontal" aria-hidden="true"></i>
              保存配置
            </button>
            <button
              v-if="selected.enabled"
              data-disable-plugin
              type="button"
              class="btn-secondary"
              @click="setEnabled(false)"
            >
              禁用
            </button>
            <button
              v-else
              data-enable-plugin
              type="button"
              class="btn-primary"
              @click="setEnabled(true)"
            >
              启用
            </button>
            <button
              v-if="!confirmingUninstall"
              data-uninstall-plugin
              type="button"
              class="btn-danger"
              @click="confirmingUninstall = true"
            >
              卸载
            </button>
            <button
              v-else
              data-confirm-uninstall-plugin
              type="button"
              class="btn-danger"
              @click="uninstall"
            >
              确认卸载
            </button>
          </template>
        </div>
      </template>
    </AppModal>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

import { resourceApi } from '../api/resources.js'
import AppModal from '../components/AppModal.vue'
import UnifiedCard from '../components/UnifiedCard.vue'


const props = defineProps({
  service: { type: Object, default: () => resourceApi },
})

const plugins = ref([])
const loading = ref(true)
const error = ref('')
const search = ref('')
const selected = ref(null)
const configuration = ref('{}')
const pluginInput = ref('{}')
const pluginResult = ref('')
const detailError = ref('')
const confirmingUninstall = ref(false)

const filteredPlugins = computed(() => {
  const query = search.value.trim().toLowerCase()
  if (!query) return plugins.value
  return plugins.value.filter((plugin) => (
    `${plugin.name} ${plugin.description} ${plugin.category}`.toLowerCase().includes(query)
  ))
})
const installedCount = computed(() => plugins.value.filter((plugin) => plugin.installed).length)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const page = await props.service.list('plugin')
    plugins.value = page.items ?? []
  } catch (cause) {
    error.value = cause?.message ?? '插件加载失败'
  } finally {
    loading.value = false
  }
}

function openDetail(plugin) {
  selected.value = plugin
  configuration.value = jsonText(plugin.configuration)
  pluginInput.value = '{}'
  pluginResult.value = ''
  detailError.value = ''
  confirmingUninstall.value = false
}

function closeDetail() {
  selected.value = null
  detailError.value = ''
  confirmingUninstall.value = false
}

async function install() {
  const parsed = parseConfiguration()
  if (!parsed) return
  await perform('install', { plugin_id: selected.value.id, configuration: parsed })
}

async function configure() {
  const parsed = parseConfiguration()
  if (!parsed) return
  await perform('configure', { plugin_id: selected.value.id, configuration: parsed })
}

async function setEnabled(enabled) {
  await perform(enabled ? 'enable' : 'disable', { plugin_id: selected.value.id })
}

async function uninstall() {
  await perform('uninstall', { plugin_id: selected.value.id })
  confirmingUninstall.value = false
}

async function callPlugin() {
  detailError.value = ''
  pluginResult.value = ''
  try {
    const result = await props.service.action('plugin', null, 'call', {
      plugin_id: selected.value.id,
      input: parseJsonObject(pluginInput.value, '插件输入'),
    })
    pluginResult.value = JSON.stringify(result, null, 2)
  } catch (cause) {
    detailError.value = cause?.message ?? '插件调用失败'
  }
}

async function perform(action, payload) {
  detailError.value = ''
  try {
    const updated = await props.service.action('plugin', null, action, payload)
    selected.value = updated
    replacePlugin(updated)
  } catch (cause) {
    detailError.value = cause?.message ?? '插件操作失败'
  }
}

function replacePlugin(plugin) {
  const index = plugins.value.findIndex((item) => item.id === plugin.id)
  if (index >= 0) plugins.value[index] = plugin
}

function parseJsonObject(value, label) {
  let parsed
  try {
    parsed = JSON.parse(value || '{}')
  } catch {
    throw new Error(`${label}必须是有效 JSON`)
  }
  if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
    throw new Error(`${label}必须是 JSON 对象`)
  }
  return parsed
}

function parseConfiguration() {
  detailError.value = ''
  try {
    return parseJsonObject(configuration.value, '配置')
  } catch (cause) {
    detailError.value = cause.message
    return null
  }
}

function jsonText(value) {
  return JSON.stringify(value ?? {}, null, 2)
}

function pluginStatus(plugin) {
  if (!plugin.installed) return '未安装'
  return plugin.enabled ? '已启用' : '已禁用'
}

onMounted(load)
</script>

<style scoped>
.plugin-summary {
  color: #5f6570;
  font-size: 0.88rem;
}

.state-band {
  padding: 24px 0;
  color: #69707c;
  text-align: center;
}

.error-state,
.form-error {
  color: #b42318;
}

.plugin-description {
  margin-bottom: 18px;
  color: #4f5663;
}

.detail-list {
  display: grid;
  grid-template-columns: 110px minmax(0, 1fr);
  gap: 10px 16px;
  margin-bottom: 18px;
}

.detail-list dt {
  color: #69707c;
}

.detail-list dd {
  min-width: 0;
  margin: 0;
}

pre {
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

.form-field,
.call-panel {
  display: grid;
  gap: 8px;
}

.form-field textarea {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #d7dce4;
  border-radius: 6px;
  font: 0.86rem/1.5 ui-monospace, SFMono-Regular, Consolas, monospace;
  letter-spacing: 0;
}

.call-panel {
  gap: 12px;
  margin-top: 20px;
  padding-top: 18px;
  border-top: 1px solid #e4e8ee;
}

.call-panel h3 {
  font-size: 0.95rem;
}

.plugin-result {
  max-height: 220px;
  padding: 12px;
  border: 1px solid #dfe4eb;
  border-radius: 6px;
  background: #f7f9fb;
}

.modal-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 20px;
}

.btn-secondary,
.btn-danger {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 9px 14px;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
}

.btn-secondary {
  border: 1px solid #d5dae2;
  background: white;
  color: #394150;
}

.btn-danger {
  border: 1px solid #f2b8b5;
  background: #fff1f0;
  color: #b42318;
}

@media (max-width: 640px) {
  .header-actions {
    align-items: stretch;
    flex-direction: column;
    gap: 12px;
  }

  .search-bar {
    width: 100%;
  }

  .detail-list {
    grid-template-columns: 1fr;
  }
}
</style>
