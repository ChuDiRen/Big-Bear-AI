<template>
  <main class="main-content">
    <header class="page-header">
      <h1 class="page-title">MCP 服务器</h1>
      <p class="page-subtitle">配置并管理模型上下文协议连接</p>
      <div class="header-actions">
        <label class="search-bar">
          <i class="ph ph-magnifying-glass" aria-hidden="true"></i>
          <input v-model="search" data-mcp-search type="search" placeholder="搜索服务器...">
        </label>
        <button data-add-mcp class="btn-primary" type="button" @click="openForm()">
          <i class="ph ph-plugs-connected" aria-hidden="true"></i>
          添加服务器
        </button>
      </div>
    </header>

    <p v-if="error" class="state-band error-state" role="alert">{{ error }}</p>
    <p v-if="loading" class="state-band" aria-busy="true">正在加载...</p>
    <p v-else-if="servers.length === 0" class="state-band">没有配置 MCP 服务器</p>
    <div v-else class="card-grid">
      <UnifiedCard
        v-for="server in servers"
        :key="server.id"
        data-mcp-card
        :item="server"
        :options="{
          badgeText: transportLabel(server.transport),
          iconName: server.icon || 'plugs-connected',
          statusText: server.health_status,
        }"
        @select="openDetail"
      />
    </div>

    <AppModal
      :open="Boolean(selected) && !formOpen"
      :title="selected?.name ?? 'MCP 服务器'"
      @close="closeDetail"
    >
      <template v-if="selected">
        <dl class="detail-list">
          <dt>传输方式</dt><dd>{{ transportLabel(selected.transport) }}</dd>
          <dt>状态</dt><dd>{{ selected.health_status }}</dd>
          <dt>描述</dt><dd>{{ selected.description || '无' }}</dd>
          <dt>配置</dt><dd><pre>{{ publicConfiguration(selected.configuration) }}</pre></dd>
          <template v-if="selected.last_error">
            <dt>最近错误</dt><dd class="error-state">{{ selected.last_error }}</dd>
          </template>
        </dl>

        <section v-if="tools.length" class="tools-panel">
          <h3>可用工具</h3>
          <label class="form-field">
            <span>工具</span>
            <select v-model="toolName">
              <option v-for="tool in tools" :key="tool.name" :value="tool.name">
                {{ tool.name }}<template v-if="tool.description"> - {{ tool.description }}</template>
              </option>
            </select>
          </label>
          <label class="form-field">
            <span>参数 JSON</span>
            <textarea v-model="toolArguments" name="mcp-tool-arguments" rows="4"></textarea>
          </label>
          <button data-call-mcp-tool type="button" class="btn-secondary" @click="callTool">
            <i class="ph ph-play" aria-hidden="true"></i>
            调用工具
          </button>
          <pre v-if="toolResult" class="tool-result">{{ toolResult }}</pre>
        </section>

        <p v-if="detailError" class="form-error" role="alert">{{ detailError }}</p>
        <div class="modal-actions">
          <button data-edit-mcp type="button" class="btn-secondary" @click="openForm(selected)">
            <i class="ph ph-pencil-simple" aria-hidden="true"></i>
            编辑
          </button>
          <button
            v-if="selected.desired_state === 'connected'"
            data-list-mcp-tools
            type="button"
            class="btn-secondary"
            @click="discoverTools"
          >
            刷新工具
          </button>
          <button
            v-if="selected.desired_state === 'connected'"
            data-disconnect-mcp
            type="button"
            class="btn-primary"
            @click="disconnect"
          >
            断开
          </button>
          <button
            v-else
            data-connect-mcp
            type="button"
            class="btn-primary"
            @click="connect"
          >
            连接
          </button>
          <button
            v-if="!confirmingDelete"
            data-delete-mcp
            type="button"
            class="btn-danger"
            @click="confirmingDelete = true"
          >
            删除
          </button>
          <button
            v-else
            data-confirm-delete-mcp
            type="button"
            class="btn-danger"
            @click="removeServer"
          >
            确认删除
          </button>
        </div>
      </template>
    </AppModal>

    <AppModal :open="formOpen" :title="editingId ? '编辑 MCP 服务器' : '添加 MCP 服务器'" @close="closeForm">
      <form data-mcp-form class="resource-form" @submit.prevent="saveServer">
        <label class="form-field">
          <span>名称</span>
          <input v-model="form.name" name="name" type="text" required>
        </label>
        <label class="form-field">
          <span>描述</span>
          <textarea v-model="form.description" name="description" rows="3"></textarea>
        </label>
        <label class="form-field">
          <span>传输方式</span>
          <select v-model="form.transport" name="transport">
            <option value="stdio">stdio</option>
            <option value="streamable_http">Streamable HTTP</option>
          </select>
        </label>

        <template v-if="form.transport === 'stdio'">
          <label class="form-field">
            <span>命令</span>
            <input v-model="form.command" name="command" type="text" required>
          </label>
          <label class="form-field">
            <span>参数（每行一项）</span>
            <textarea v-model="form.args" name="args" rows="3"></textarea>
          </label>
          <label class="form-field">
            <span>工作目录</span>
            <input v-model="form.cwd" name="cwd" type="text">
          </label>
          <label class="form-field">
            <span>环境变量引用 JSON</span>
            <textarea v-model="form.environment" name="environment" rows="3"></textarea>
          </label>
        </template>
        <template v-else>
          <label class="form-field">
            <span>URL</span>
            <input v-model="form.url" name="url" type="url" required>
          </label>
          <label class="form-field">
            <span>请求头引用 JSON</span>
            <textarea v-model="form.headers" name="headers" rows="3"></textarea>
          </label>
        </template>

        <p v-if="formError" class="form-error" role="alert">{{ formError }}</p>
        <div class="modal-actions">
          <button type="button" class="btn-secondary" @click="closeForm">取消</button>
          <button type="submit" class="btn-primary" :disabled="saving">
            {{ saving ? '保存中...' : '保存' }}
          </button>
        </div>
      </form>
    </AppModal>
  </main>
</template>

<script setup>
import { onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'

import { resourceApi } from '../api/resources.js'
import AppModal from '../components/AppModal.vue'
import UnifiedCard from '../components/UnifiedCard.vue'


const props = defineProps({
  service: { type: Object, default: () => resourceApi },
})

const servers = ref([])
const loading = ref(true)
const error = ref('')
const search = ref('')
const selected = ref(null)
const detailError = ref('')
const confirmingDelete = ref(false)
const formOpen = ref(false)
const editingId = ref(null)
const saving = ref(false)
const formError = ref('')
const tools = ref([])
const toolName = ref('')
const toolArguments = ref('{}')
const toolResult = ref('')
const form = reactive({
  name: '',
  description: '',
  transport: 'stdio',
  command: '',
  args: '',
  cwd: '',
  environment: '{}',
  url: '',
  headers: '{}',
})
let searchTimer

async function load() {
  loading.value = true
  error.value = ''
  try {
    const page = await props.service.list('mcp', { search: search.value.trim(), limit: 100 })
    servers.value = page.items ?? []
  } catch (cause) {
    error.value = cause?.message ?? 'MCP 服务器加载失败'
  } finally {
    loading.value = false
  }
}

function openDetail(server) {
  selected.value = server
  detailError.value = ''
  confirmingDelete.value = false
  tools.value = []
  toolName.value = ''
  toolArguments.value = '{}'
  toolResult.value = ''
}

function closeDetail() {
  selected.value = null
  detailError.value = ''
  confirmingDelete.value = false
  tools.value = []
}

function openForm(server = null) {
  editingId.value = server?.id ?? null
  const configuration = server?.configuration ?? {}
  form.name = server?.name ?? ''
  form.description = server?.description ?? ''
  form.transport = server?.transport || 'stdio'
  form.command = configuration.command ?? ''
  form.args = (configuration.args ?? []).join('\n')
  form.cwd = configuration.cwd ?? ''
  form.environment = JSON.stringify(configuration.env ?? {}, null, 2)
  form.url = configuration.url ?? ''
  form.headers = JSON.stringify(configuration.headers ?? {}, null, 2)
  formError.value = ''
  formOpen.value = true
}

function closeForm() {
  formOpen.value = false
  formError.value = ''
}

async function saveServer() {
  saving.value = true
  formError.value = ''
  try {
    const configuration = form.transport === 'stdio'
      ? stdioConfiguration()
      : httpConfiguration()
    const payload = {
      name: form.name.trim(),
      description: form.description.trim(),
      transport: form.transport,
      configuration,
    }
    if (editingId.value) {
      await props.service.update('mcp', editingId.value, payload)
    } else {
      await props.service.create('mcp', payload)
    }
    closeForm()
    closeDetail()
    await load()
  } catch (cause) {
    formError.value = cause?.message ?? 'MCP 配置保存失败'
  } finally {
    saving.value = false
  }
}

function stdioConfiguration() {
  const configuration = {
    command: form.command.trim(),
    args: form.args.split(/\r?\n/).map((item) => item.trim()).filter(Boolean),
    env: parseObject(form.environment, '环境变量引用'),
  }
  if (form.cwd.trim()) configuration.cwd = form.cwd.trim()
  return configuration
}

function httpConfiguration() {
  return {
    url: form.url.trim(),
    headers: parseObject(form.headers, '请求头引用'),
  }
}

function parseObject(value, label) {
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

async function connect() {
  detailError.value = ''
  try {
    const connected = await props.service.action('mcp', selected.value.id, 'connect')
    selected.value = connected
    tools.value = connected.tools ?? await props.service.action(
      'mcp', selected.value.id, 'list_tools',
    )
    toolName.value = tools.value[0]?.name ?? ''
    replaceServer(connected)
  } catch (cause) {
    detailError.value = cause?.message ?? 'MCP 连接失败'
  }
}

async function disconnect() {
  detailError.value = ''
  try {
    const disconnected = await props.service.action('mcp', selected.value.id, 'disconnect')
    selected.value = disconnected
    tools.value = []
    toolResult.value = ''
    replaceServer(disconnected)
  } catch (cause) {
    detailError.value = cause?.message ?? 'MCP 断开失败'
  }
}

async function discoverTools() {
  detailError.value = ''
  try {
    tools.value = await props.service.action('mcp', selected.value.id, 'list_tools')
    toolName.value = tools.value[0]?.name ?? ''
  } catch (cause) {
    detailError.value = cause?.message ?? '工具发现失败'
  }
}

async function callTool() {
  detailError.value = ''
  toolResult.value = ''
  try {
    const result = await props.service.action('mcp', selected.value.id, 'call', {
      tool_name: toolName.value,
      arguments: parseObject(toolArguments.value, '工具参数'),
    })
    toolResult.value = JSON.stringify(result, null, 2)
  } catch (cause) {
    detailError.value = cause?.message ?? '工具调用失败'
  }
}

async function removeServer() {
  try {
    await props.service.remove('mcp', selected.value.id)
    closeDetail()
    await load()
  } catch (cause) {
    error.value = cause?.message ?? 'MCP 服务器删除失败'
    closeDetail()
  }
}

function replaceServer(server) {
  const index = servers.value.findIndex((item) => item.id === server.id)
  if (index >= 0) servers.value[index] = server
}

function transportLabel(transport) {
  return transport === 'streamable_http' ? 'HTTP' : transport || '未配置'
}

function publicConfiguration(configuration) {
  return JSON.stringify(configuration ?? {}, null, 2)
}

watch(search, () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(load, 250)
})
onMounted(load)
onBeforeUnmount(() => clearTimeout(searchTimer))
</script>

<style scoped>
.state-band {
  padding: 24px 0;
  color: #69707c;
  text-align: center;
}

.error-state,
.form-error {
  color: #b42318;
}

.detail-list {
  display: grid;
  grid-template-columns: 110px minmax(0, 1fr);
  gap: 10px 16px;
}

.detail-list dt {
  color: #69707c;
}

.detail-list dd {
  min-width: 0;
  margin: 0;
  overflow-wrap: anywhere;
}

pre {
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

.resource-form,
.form-field,
.tools-panel {
  display: grid;
  gap: 8px;
}

.resource-form,
.tools-panel {
  gap: 15px;
}

.form-field input,
.form-field textarea,
.form-field select {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #d7dce4;
  border-radius: 6px;
  background: white;
  font: inherit;
  letter-spacing: 0;
}

.tools-panel {
  margin-top: 20px;
  padding-top: 18px;
  border-top: 1px solid #e4e8ee;
}

.tools-panel h3 {
  font-size: 0.95rem;
}

.tool-result {
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
