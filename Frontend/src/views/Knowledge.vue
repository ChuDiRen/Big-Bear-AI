<template>
  <main class="main-content">
    <header class="page-header">
      <h1 class="page-title">知识库</h1>
      <p class="page-subtitle">上传、检索并管理测试知识</p>
      <div class="header-actions knowledge-actions">
        <form data-knowledge-search-form class="search-bar" @submit.prevent="searchContent">
          <i class="ph ph-magnifying-glass" aria-hidden="true"></i>
          <input
            v-model="query"
            data-knowledge-query
            type="search"
            placeholder="检索文档内容..."
          >
          <button class="search-submit" type="submit" title="检索内容">
            <i class="ph ph-arrow-right" aria-hidden="true"></i>
          </button>
        </form>
        <button data-upload-document class="btn-primary" type="button" @click="openUpload">
          <i class="ph ph-upload-simple" aria-hidden="true"></i>
          上传文档
        </button>
      </div>
    </header>

    <p v-if="error" class="state-band error-state" role="alert">{{ error }}</p>

    <section v-if="searchPerformed" class="result-band" aria-live="polite">
      <div class="section-heading">
        <h2>检索结果</h2>
        <button type="button" class="icon-button" title="关闭检索结果" @click="clearSearch">
          <i class="ph ph-x" aria-hidden="true"></i>
        </button>
      </div>
      <p v-if="searching" class="state-band">正在检索...</p>
      <p v-else-if="searchResults.length === 0" class="state-band">未找到匹配内容</p>
      <ol v-else class="search-results">
        <li v-for="result in searchResults" :key="result.chunk_id">
          <strong>{{ result.title }}</strong>
          <p>{{ result.content }}</p>
        </li>
      </ol>
    </section>

    <p v-if="loading" class="state-band" aria-busy="true">正在加载...</p>
    <p v-else-if="documents.length === 0" class="state-band">知识库中还没有文档</p>
    <div v-else class="card-grid">
      <UnifiedCard
        v-for="document in documents"
        :key="document.id"
        data-document-card
        :item="document"
        :options="{
          badgeText: document.index_status === 'ready' ? '已索引' : document.index_status,
          showIcon: true,
          iconName: 'book-open',
        }"
        @select="openDetail"
      />
    </div>

    <AppModal :open="Boolean(selected)" :title="selected?.title ?? '文档详情'" @close="closeDetail">
      <dl v-if="selected" class="detail-list">
        <dt>文件名</dt><dd>{{ selected.filename || '内置知识' }}</dd>
        <dt>类型</dt><dd>{{ selected.media_type || '文本' }}</dd>
        <dt>大小</dt><dd>{{ formatBytes(selected.size_bytes) }}</dd>
        <dt>索引状态</dt><dd>{{ selected.index_status }}</dd>
        <dt>描述</dt><dd>{{ selected.description || '无' }}</dd>
      </dl>
      <div v-if="selected && !selected.read_only" class="modal-actions">
        <button
          v-if="!confirmingDelete"
          data-delete-document
          type="button"
          class="btn-danger"
          @click="confirmingDelete = true"
        >
          删除文档
        </button>
        <button
          v-else
          data-confirm-delete-document
          type="button"
          class="btn-danger"
          @click="removeDocument"
        >
          确认删除
        </button>
      </div>
    </AppModal>

    <AppModal :open="uploadOpen" title="上传文档" @close="closeUpload">
      <form data-upload-form class="resource-form" @submit.prevent="uploadDocument">
        <label class="form-field">
          <span>文件</span>
          <input
            data-document-file
            type="file"
            accept=".txt,.md,.json,.csv,.pdf,.docx"
            required
            @change="selectFile"
          >
        </label>
        <label class="form-field">
          <span>名称</span>
          <input v-model="upload.title" name="title" type="text" placeholder="默认使用文件名">
        </label>
        <label class="form-field">
          <span>描述</span>
          <textarea v-model="upload.description" name="description" rows="3"></textarea>
        </label>
        <p v-if="formError" class="form-error" role="alert">{{ formError }}</p>
        <div class="modal-actions">
          <button type="button" class="btn-secondary" @click="closeUpload">取消</button>
          <button type="submit" class="btn-primary" :disabled="saving">
            {{ saving ? '上传中...' : '上传' }}
          </button>
        </div>
      </form>
    </AppModal>
  </main>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'

import { resourceApi } from '../api/resources.js'
import AppModal from '../components/AppModal.vue'
import UnifiedCard from '../components/UnifiedCard.vue'


const props = defineProps({
  service: { type: Object, default: () => resourceApi },
})

const documents = ref([])
const loading = ref(true)
const error = ref('')
const query = ref('')
const searchResults = ref([])
const searchPerformed = ref(false)
const searching = ref(false)
const selected = ref(null)
const confirmingDelete = ref(false)
const uploadOpen = ref(false)
const uploadFile = ref(null)
const saving = ref(false)
const formError = ref('')
const upload = reactive({ title: '', description: '' })

async function load() {
  loading.value = true
  error.value = ''
  try {
    const page = await props.service.list('document', { search: '', limit: 100 })
    documents.value = page.items ?? []
  } catch (cause) {
    error.value = cause?.message ?? '知识库加载失败'
  } finally {
    loading.value = false
  }
}

async function searchContent() {
  const text = query.value.trim()
  if (!text) return
  searchPerformed.value = true
  searching.value = true
  error.value = ''
  try {
    searchResults.value = await props.service.action('document', null, 'search', {
      query: text,
      limit: 8,
    })
  } catch (cause) {
    error.value = cause?.message ?? '知识检索失败'
    searchResults.value = []
  } finally {
    searching.value = false
  }
}

function clearSearch() {
  searchPerformed.value = false
  searchResults.value = []
}

function openDetail(document) {
  selected.value = document
  confirmingDelete.value = false
}

function closeDetail() {
  selected.value = null
  confirmingDelete.value = false
}

function openUpload() {
  upload.title = ''
  upload.description = ''
  uploadFile.value = null
  formError.value = ''
  uploadOpen.value = true
}

function closeUpload() {
  uploadOpen.value = false
  formError.value = ''
}

function selectFile(event) {
  uploadFile.value = event.target.files?.[0] ?? null
}

async function uploadDocument() {
  if (!uploadFile.value) {
    formError.value = '请选择文件'
    return
  }
  saving.value = true
  formError.value = ''
  try {
    await props.service.action('document', null, 'upload', {
      filename: uploadFile.value.name,
      media_type: uploadFile.value.type || 'application/octet-stream',
      content_base64: await readFileBase64(uploadFile.value),
      title: upload.title.trim(),
      description: upload.description.trim(),
    })
    closeUpload()
    await load()
  } catch (cause) {
    formError.value = cause?.message ?? '文档上传失败'
  } finally {
    saving.value = false
  }
}

async function removeDocument() {
  try {
    await props.service.remove('document', selected.value.id)
    closeDetail()
    await load()
  } catch (cause) {
    error.value = cause?.message ?? '文档删除失败'
    closeDetail()
  }
}

function readFileBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(new Error('文件读取失败'))
    reader.onload = () => resolve(String(reader.result).split(',', 2)[1] ?? '')
    reader.readAsDataURL(file)
  })
}

function formatBytes(value) {
  if (!value) return '内置'
  if (value < 1024) return `${value} B`
  return `${(value / 1024).toFixed(1)} KiB`
}

onMounted(load)
</script>

<style scoped>
.knowledge-actions,
.section-heading,
.modal-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.search-bar {
  padding-block: 7px;
}

.search-submit,
.icon-button {
  display: inline-grid;
  width: 32px;
  height: 32px;
  flex: 0 0 auto;
  place-items: center;
  border: 0;
  border-radius: 6px;
  background: #eef2f7;
  color: #384151;
  cursor: pointer;
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

.result-band {
  margin-bottom: 24px;
  padding-block: 18px;
  border-block: 1px solid #dfe4eb;
}

.section-heading {
  justify-content: space-between;
}

.section-heading h2 {
  font-size: 1rem;
}

.search-results {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}

.search-results li {
  padding: 12px 14px;
  border-left: 3px solid #2563eb;
  background: #fff;
}

.search-results p {
  margin-top: 4px;
  color: #5f6570;
  overflow-wrap: anywhere;
}

.detail-list {
  display: grid;
  grid-template-columns: 100px 1fr;
  gap: 10px 16px;
}

.detail-list dt {
  color: #69707c;
}

.detail-list dd {
  margin: 0;
  overflow-wrap: anywhere;
}

.resource-form,
.form-field {
  display: grid;
  gap: 8px;
}

.resource-form {
  gap: 16px;
}

.form-field input,
.form-field textarea {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #d7dce4;
  border-radius: 6px;
  font: inherit;
  letter-spacing: 0;
}

.modal-actions {
  justify-content: flex-end;
  margin-top: 20px;
}

.btn-secondary,
.btn-danger {
  padding: 9px 14px;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
}

.btn-secondary {
  border: 1px solid #d5dae2;
  background: white;
}

.btn-danger {
  border: 1px solid #f2b8b5;
  background: #fff1f0;
  color: #b42318;
}

@media (max-width: 640px) {
  .knowledge-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .search-bar {
    width: 100%;
  }

  .detail-list {
    grid-template-columns: 1fr;
  }
}
</style>
