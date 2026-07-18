<template>
  <main class="main-content home-content">
    <header class="workspace-header">
      <div>
        <p class="workspace-kicker">大熊AI</p>
        <h1>测试工作台</h1>
      </div>
      <button
        data-new-conversation
        type="button"
        class="icon-command"
        title="新建对话"
        @click="newConversation"
      >
        <i class="ph ph-note-pencil" aria-hidden="true"></i>
      </button>
    </header>

    <div v-if="contextItems.length || selectedProjectId" class="context-strip" aria-label="当前上下文">
      <span v-if="selectedProjectId" class="context-chip">
        <i class="ph ph-folder" aria-hidden="true"></i>
        {{ selectedProjectName || selectedProjectId }}
      </span>
      <span v-for="item in contextItems" :key="item.key" class="context-chip">
        <i :class="['ph', item.icon]" aria-hidden="true"></i>
        {{ item.label }}
      </span>
    </div>

    <section v-if="promptVariableNames.length" class="prompt-variables" aria-label="Prompt 变量">
      <label v-for="name in promptVariableNames" :key="name">
        <span>{{ name }}</span>
        <input
          v-model="promptVariables[name]"
          :data-prompt-variable="name"
          type="text"
          :placeholder="name"
          :disabled="streaming"
        >
      </label>
    </section>

    <section class="conversation" aria-live="polite">
      <div v-if="messages.length === 0" class="empty-conversation">
        <i class="ph ph-chats-circle" aria-hidden="true"></i>
        <p>新对话</p>
      </div>
      <div v-else class="message-list">
        <article
          v-for="message in messages"
          :key="message.id"
          data-chat-message
          class="message-row"
          :class="`message-${message.role}`"
        >
          <div class="message-avatar" aria-hidden="true">
            <i :class="message.role === 'user' ? 'ph ph-user' : 'ph ph-robot'"></i>
          </div>
          <div class="message-body">
            <span class="message-author">{{ message.role === 'user' ? '你' : '大熊AI' }}</span>
            <p>{{ message.content }}</p>
            <span v-if="message.pending" class="typing-indicator">正在生成...</span>
          </div>
        </article>
      </div>
    </section>

    <div v-if="activity" class="activity-line">
      <i class="ph ph-activity" aria-hidden="true"></i>
      {{ activity }}
    </div>

    <div v-if="error" class="error-line" role="alert">
      <span>{{ error }}</span>
      <button data-retry-message type="button" class="text-command" @click="retryLast">
        <i class="ph ph-arrow-clockwise" aria-hidden="true"></i>
        重试
      </button>
    </div>

    <section class="composer" aria-label="发送消息">
      <textarea
        v-model="input"
        data-chat-input
        rows="4"
        placeholder="输入测试目标、接口描述或问题"
        :disabled="streaming"
        @keydown.enter.exact.prevent="sendMessage()"
      ></textarea>
      <div class="composer-footer">
        <div class="mode-segments" aria-label="对话模式">
          <button
            v-for="option in modes"
            :key="option.value"
            :data-mode="option.value"
            type="button"
            :class="{ active: mode === option.value }"
            :title="option.label"
            @click="mode = option.value"
          >
            <i :class="['ph', option.icon]" aria-hidden="true"></i>
            <span>{{ option.label }}</span>
          </button>
        </div>
        <button
          v-if="streaming"
          data-stop-message
          type="button"
          class="send-command stop-command"
          title="停止生成"
          @click="stopGeneration"
        >
          <i class="ph-fill ph-stop" aria-hidden="true"></i>
        </button>
        <button
          v-else
          data-send-message
          type="button"
          class="send-command"
          title="发送"
          :disabled="!input.trim()"
          @click="sendMessage()"
        >
          <i class="ph-fill ph-paper-plane-right" aria-hidden="true"></i>
        </button>
      </div>
    </section>

    <div class="quick-actions">
      <button data-start-testing type="button" class="action-btn" @click="startTesting">
        <i class="ph ph-play-circle" aria-hidden="true"></i>
        <span>开始测试</span>
      </button>
      <button data-open-design type="button" class="action-btn" @click="openDesignChooser">
        <i class="ph ph-folder-open" aria-hidden="true"></i>
        <span>打开测试设计</span>
      </button>
      <button data-new-project type="button" class="action-btn" @click="openProjectForm">
        <i class="ph ph-plus-circle" aria-hidden="true"></i>
        <span>新建测试项目</span>
      </button>
    </div>

    <AppModal :open="designOpen" title="打开测试设计" @close="designOpen = false">
      <label class="modal-search">
        <i class="ph ph-magnifying-glass" aria-hidden="true"></i>
        <input v-model="designSearch" type="search" placeholder="搜索项目或设计...">
      </label>
      <p v-if="designsLoading" class="modal-state">正在加载...</p>
      <p v-else-if="filteredDesigns.length === 0" class="modal-state">没有测试设计</p>
      <div v-else class="design-list">
        <button
          v-for="design in filteredDesigns"
          :key="design.id"
          :data-design="design.id"
          type="button"
          @click="chooseDesign(design)"
        >
          <strong>{{ design.title }}</strong>
          <span>{{ projectName(design.project_id) }}</span>
          <p>{{ design.content || '空白设计' }}</p>
        </button>
      </div>
    </AppModal>

    <AppModal :open="projectOpen" title="新建测试项目" @close="projectOpen = false">
      <form data-project-form class="project-form" @submit.prevent="createProject">
        <label>
          <span>项目名称</span>
          <input v-model="projectForm.name" name="project-name" type="text" required>
        </label>
        <label>
          <span>项目描述</span>
          <textarea v-model="projectForm.description" name="project-description" rows="4"></textarea>
        </label>
        <p v-if="projectError" class="form-error" role="alert">{{ projectError }}</p>
        <div class="modal-actions">
          <button type="button" class="secondary-command" @click="projectOpen = false">取消</button>
          <button type="submit" class="primary-command" :disabled="projectSaving">
            {{ projectSaving ? '创建中...' : '创建' }}
          </button>
        </div>
      </form>
    </AppModal>
  </main>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { langGraphApi } from '../api/langgraph.js'
import { resourceApi } from '../api/resources.js'
import AppModal from '../components/AppModal.vue'


const THREAD_KEY = 'big-bear-thread-id'
const props = defineProps({
  graphApi: { type: Object, default: () => langGraphApi },
  service: { type: Object, default: () => resourceApi },
  storage: { type: Object, default: () => window.localStorage },
})
const route = useRoute()

const modes = [
  { value: 'auto', label: 'Auto', icon: 'ph-magic-wand' },
  { value: 'design', label: '设计', icon: 'ph-blueprint' },
  { value: 'analysis', label: '分析', icon: 'ph-chart-line-up' },
  { value: 'execution', label: '执行', icon: 'ph-play' },
]
const input = ref('')
const mode = ref('auto')
const messages = ref([])
const threadId = ref(props.storage.getItem(THREAD_KEY) || '')
const streaming = ref(false)
const activeHandle = ref(null)
const stopRequested = ref(false)
const error = ref('')
const activity = ref('')
const lastRequest = ref(null)
const contextItems = ref([])
const promptVariableNames = ref([])
const promptVariables = reactive({})
const selectedProjectId = ref('')
const selectedProjectName = ref('')
const designOpen = ref(false)
const designsLoading = ref(false)
const designSearch = ref('')
const projects = ref([])
const designs = ref([])
const projectOpen = ref(false)
const projectSaving = ref(false)
const projectError = ref('')
const projectForm = reactive({ name: '', description: '' })
let messageSequence = 0

const filteredDesigns = computed(() => {
  const query = designSearch.value.trim().toLowerCase()
  if (!query) return designs.value
  return designs.value.filter((design) => (
    `${design.title} ${design.content} ${projectName(design.project_id)}`
      .toLowerCase()
      .includes(query)
  ))
})

async function sendMessage(text = input.value, { appendUser = true } = {}) {
  const content = String(text).trim()
  if (!content || streaming.value) return

  error.value = ''
  activity.value = ''
  stopRequested.value = false
  if (!threadId.value) {
    threadId.value = await props.graphApi.createThread()
    props.storage.setItem(THREAD_KEY, threadId.value)
  }

  if (appendUser) {
    messages.value.push(createMessage('user', content))
    input.value = ''
  }
  const assistant = createMessage('assistant', '', true)
  messages.value.push(assistant)
  lastRequest.value = { text: content, assistantId: assistant.id }
  streaming.value = true

  const handle = props.graphApi.streamAssistant({
    threadId: threadId.value,
    input: { messages: [{ role: 'user', content }] },
    context: currentContext(),
    onEvent: (event) => applyStreamEvent(assistant, event),
  })
  activeHandle.value = handle

  try {
    await handle.done
    assistant.pending = false
    if (!assistant.content && !stopRequested.value) {
      assistant.content = '未收到模型输出。'
    }
  } catch (cause) {
    assistant.pending = false
    if (!stopRequested.value) {
      error.value = cause?.message ?? '对话运行失败'
      if (!assistant.content) removeMessage(assistant.id)
    }
  } finally {
    if (activeHandle.value === handle) activeHandle.value = null
    streaming.value = false
  }
}

function applyStreamEvent(assistant, event) {
  if (event.type === 'message' && event.text) {
    assistant.content += event.text
    return
  }
  if (event.type === 'custom') {
    activity.value = eventLabel(event.data)
  }
}

async function stopGeneration() {
  if (!activeHandle.value) return
  stopRequested.value = true
  await activeHandle.value.cancel()
  activity.value = '已停止生成'
  streaming.value = false
}

async function retryLast() {
  if (!lastRequest.value || streaming.value) return
  error.value = ''
  removeMessage(lastRequest.value.assistantId)
  await sendMessage(lastRequest.value.text, { appendUser: false })
}

async function newConversation() {
  if (streaming.value) await stopGeneration()
  threadId.value = ''
  messages.value = []
  error.value = ''
  activity.value = ''
  lastRequest.value = null
  props.storage.removeItem(THREAD_KEY)
}

function startTesting() {
  sendMessage('请根据当前项目和已选上下文开始测试，并给出可执行的测试步骤。')
}

async function openDesignChooser() {
  designOpen.value = true
  designsLoading.value = true
  designSearch.value = ''
  try {
    const [projectPage, designPage] = await Promise.all([
      props.service.list('project', { search: '', limit: 100 }),
      props.service.list('design', { search: '', limit: 100 }),
    ])
    projects.value = projectPage.items ?? []
    designs.value = designPage.items ?? []
  } catch (cause) {
    error.value = cause?.message ?? '测试设计加载失败'
  } finally {
    designsLoading.value = false
  }
}

function chooseDesign(design) {
  selectedProjectId.value = design.project_id
  selectedProjectName.value = projectName(design.project_id)
  input.value = `继续完善测试设计「${design.title}」：\n${design.content || ''}`.trim()
  designOpen.value = false
}

function openProjectForm() {
  projectForm.name = ''
  projectForm.description = ''
  projectError.value = ''
  projectOpen.value = true
}

async function createProject() {
  const name = projectForm.name.trim()
  if (!name) {
    projectError.value = '项目名称不能为空'
    return
  }
  projectSaving.value = true
  projectError.value = ''
  try {
    const project = await props.service.create('project', {
      name,
      description: projectForm.description.trim(),
      status: 'draft',
    })
    selectedProjectId.value = project.id
    selectedProjectName.value = project.name
    projectOpen.value = false
  } catch (cause) {
    projectError.value = cause?.message ?? '项目创建失败'
  } finally {
    projectSaving.value = false
  }
}

function currentContext() {
  const context = { mode: mode.value }
  if (selectedProjectId.value) context.project_id = selectedProjectId.value
  for (const key of ['agent_id', 'prompt_id', 'rule_id']) {
    if (typeof route.query[key] === 'string' && route.query[key]) {
      context[key] = route.query[key]
    }
  }
  if (context.prompt_id && promptVariableNames.value.length) {
    context.prompt_variables = Object.fromEntries(
      promptVariableNames.value.map((name) => [name, promptVariables[name] ?? '']),
    )
  }
  return context
}

async function loadContextItems() {
  const definitions = [
    ['agent_id', 'agent', 'ph-robot'],
    ['prompt_id', 'prompt', 'ph-file-text'],
    ['rule_id', 'rule', 'ph-scroll'],
  ]
  const items = await Promise.all(definitions.map(async ([key, resource, icon]) => {
    const id = route.query[key]
    if (typeof id !== 'string' || !id) return null
    try {
      const item = await props.service.get(resource, id)
      return {
        key,
        icon,
        label: item.name ?? item.title ?? id,
        variables: resource === 'prompt' && Array.isArray(item.variables) ? item.variables : [],
      }
    } catch {
      return { key, icon, label: id }
    }
  }))
  contextItems.value = items.filter(Boolean)
  const variableNames = items
    .find((item) => item?.key === 'prompt_id')
    ?.variables
    ?.filter((name) => typeof name === 'string' && name) ?? []
  promptVariableNames.value = [...new Set(variableNames)]
  for (const name of Object.keys(promptVariables)) {
    if (!promptVariableNames.value.includes(name)) delete promptVariables[name]
  }
  for (const name of promptVariableNames.value) {
    if (!(name in promptVariables)) promptVariables[name] = ''
  }
}

function createMessage(role, content, pending = false) {
  messageSequence += 1
  return { id: `message-${messageSequence}`, role, content, pending }
}

function removeMessage(id) {
  messages.value = messages.value.filter((message) => message.id !== id)
}

function projectName(projectId) {
  return projects.value.find((project) => project.id === projectId)?.name ?? projectId
}

function eventLabel(data) {
  if (typeof data === 'string') return data
  if (data?.stage) return String(data.stage)
  if (data?.message) return String(data.message)
  return '处理中'
}

watch(() => route.query, loadContextItems, { deep: true })
onMounted(loadContextItems)
</script>

<style scoped>
.home-content {
  display: flex;
  min-width: 0;
  min-height: 100%;
  align-items: stretch;
  justify-content: flex-start;
  padding: 0;
  background: #f7f8fa;
}

.workspace-header,
.context-strip,
.prompt-variables,
.conversation,
.composer,
.quick-actions,
.activity-line,
.error-line {
  width: min(920px, calc(100% - 48px));
  margin-inline: auto;
}

.workspace-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 28px;
}

.workspace-kicker {
  color: #2563eb;
  font-size: 0.78rem;
  font-weight: 700;
}

.workspace-header h1 {
  margin-top: 2px;
  font-size: 1.35rem;
  letter-spacing: 0;
}

.icon-command,
.send-command {
  display: inline-grid;
  place-items: center;
  border: 0;
  cursor: pointer;
}

.icon-command {
  width: 38px;
  height: 38px;
  border: 1px solid #dce1e8;
  border-radius: 7px;
  background: white;
  color: #303846;
}

.context-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding-top: 14px;
}

.context-chip {
  display: inline-flex;
  max-width: 240px;
  align-items: center;
  gap: 6px;
  padding: 5px 9px;
  border: 1px solid #d9dfe7;
  border-radius: 5px;
  background: white;
  color: #4c5564;
  font-size: 0.78rem;
  overflow-wrap: anywhere;
}

.prompt-variables {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
  padding: 12px 0 0;
}

.prompt-variables label {
  display: grid;
  gap: 5px;
  min-width: 0;
  color: #4b5563;
  font-size: 12px;
}

.prompt-variables input {
  width: 100%;
  min-width: 0;
  height: 38px;
  padding: 0 11px;
  border: 1px solid #d9dee7;
  border-radius: 6px;
  background: #fff;
  color: #1f2937;
  font: inherit;
}

.prompt-variables input:focus {
  border-color: #2563eb;
  outline: 2px solid rgb(37 99 235 / 14%);
}

.conversation {
  flex: 1 1 auto;
  min-height: 260px;
  padding-block: 26px 18px;
}

.empty-conversation {
  display: grid;
  min-height: 240px;
  place-content: center;
  color: #9299a5;
  text-align: center;
}

.empty-conversation i {
  font-size: 2rem;
}

.message-list {
  display: grid;
  gap: 22px;
}

.message-row {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  gap: 12px;
}

.message-avatar {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border: 1px solid #dfe4eb;
  border-radius: 7px;
  background: white;
  color: #445064;
}

.message-assistant .message-avatar {
  border-color: #bfd5ff;
  background: #eaf2ff;
  color: #1d5dc4;
}

.message-body {
  min-width: 0;
  padding-top: 2px;
}

.message-author {
  display: block;
  margin-bottom: 5px;
  color: #69717e;
  font-size: 0.75rem;
  font-weight: 650;
}

.message-body p {
  color: #252b35;
  line-height: 1.65;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.typing-indicator {
  color: #7b8492;
  font-size: 0.78rem;
}

.activity-line,
.error-line {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  padding: 8px 10px;
  border-left: 3px solid #4f7fd8;
  background: #eef4ff;
  color: #4a5d7f;
  font-size: 0.8rem;
}

.error-line {
  justify-content: space-between;
  border-left-color: #c43c35;
  background: #fff0ef;
  color: #a72d27;
}

.text-command {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: 0;
  background: transparent;
  color: inherit;
  font-weight: 650;
  cursor: pointer;
}

.composer {
  flex: 0 0 auto;
  border: 1px solid #d7dde6;
  border-radius: 8px;
  background: white;
  box-shadow: 0 7px 20px rgb(33 45 68 / 8%);
}

.composer textarea {
  width: 100%;
  min-height: 92px;
  padding: 16px;
  border: 0;
  background: transparent;
  color: #202630;
  font: inherit;
  letter-spacing: 0;
  outline: 0;
  resize: vertical;
}

.composer-footer {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
  padding: 10px;
  border-top: 1px solid #edf0f4;
}

.mode-segments {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
  padding: 3px;
  border: 1px solid #e0e4ea;
  border-radius: 6px;
  background: #f4f6f8;
}

.mode-segments button {
  display: inline-flex;
  min-height: 30px;
  align-items: center;
  gap: 5px;
  padding: 5px 8px;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: #68717f;
  cursor: pointer;
  font-size: 0.76rem;
}

.mode-segments button.active {
  background: white;
  box-shadow: 0 1px 3px rgb(30 38 52 / 12%);
  color: #1f5ebd;
}

.send-command {
  width: 38px;
  height: 38px;
  border-radius: 7px;
  background: #2563eb;
  color: white;
  font-size: 1rem;
}

.send-command:disabled {
  background: #b8c4d6;
  cursor: default;
}

.stop-command {
  background: #c43c35;
}

.quick-actions {
  display: flex;
  flex: 0 0 auto;
  flex-wrap: wrap;
  justify-content: flex-start;
  gap: 8px;
  margin-top: 12px;
  padding-bottom: 28px;
}

.action-btn {
  display: inline-flex;
  min-height: 36px;
  align-items: center;
  gap: 7px;
  padding: 7px 11px;
  border: 1px solid #d8dee7;
  border-radius: 6px;
  background: white;
  color: #4f5866;
  cursor: pointer;
  font-size: 0.8rem;
}

.modal-search {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 11px;
  border: 1px solid #d7dde6;
  border-radius: 6px;
}

.modal-search input {
  width: 100%;
  border: 0;
  font: inherit;
}

.modal-state {
  padding: 24px 0;
  color: #7a8290;
  text-align: center;
}

.design-list {
  display: grid;
  gap: 8px;
  margin-top: 14px;
}

.design-list button {
  display: grid;
  gap: 3px;
  width: 100%;
  padding: 12px;
  border: 1px solid #dfe4eb;
  border-radius: 6px;
  background: white;
  color: #2e3540;
  text-align: left;
  cursor: pointer;
}

.design-list button:hover {
  border-color: #8eb5f4;
  background: #f7faff;
}

.design-list span,
.design-list p {
  color: #727b88;
  font-size: 0.78rem;
}

.project-form,
.project-form label {
  display: grid;
  gap: 8px;
}

.project-form {
  gap: 16px;
}

.project-form input,
.project-form textarea {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #d7dde6;
  border-radius: 6px;
  font: inherit;
  letter-spacing: 0;
}

.form-error {
  color: #b42318;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.secondary-command,
.primary-command {
  padding: 9px 14px;
  border-radius: 6px;
  font-weight: 650;
  cursor: pointer;
}

.secondary-command {
  border: 1px solid #d5dae2;
  background: white;
}

.primary-command {
  border: 1px solid #2563eb;
  background: #2563eb;
  color: white;
}

@media (max-width: 700px) {
  .workspace-header,
  .context-strip,
  .conversation,
  .composer,
  .quick-actions,
  .activity-line,
  .error-line {
    width: min(100% - 24px, 920px);
  }

  .workspace-header {
    padding-top: 18px;
  }

  .conversation {
    min-height: 220px;
  }

  .composer-footer {
    align-items: stretch;
  }

  .mode-segments {
    flex: 1;
  }

  .mode-segments button span {
    display: none;
  }

  .quick-actions {
    display: grid;
    grid-template-columns: 1fr;
  }

  .action-btn {
    justify-content: flex-start;
  }
}
</style>
