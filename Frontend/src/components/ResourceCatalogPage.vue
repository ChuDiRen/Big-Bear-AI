<template>
  <main class="main-content">
    <header class="page-header">
      <h1 class="page-title">{{ title }}</h1>
      <p class="page-subtitle">{{ subtitle }}</p>
      <div class="header-actions">
        <label class="search-bar">
          <i class="ph ph-magnifying-glass" aria-hidden="true"></i>
          <input
            v-model="search"
            data-resource-search
            type="search"
            :placeholder="searchPlaceholder"
          >
        </label>
        <button data-create-resource type="button" class="btn-primary" @click="openCreate">
          <i class="ph ph-plus" aria-hidden="true"></i>
          {{ actionLabel }}
        </button>
      </div>
    </header>

    <div v-if="loading" class="state-band" aria-busy="true">正在加载...</div>
    <div v-else-if="error" class="state-band error-state" role="alert">
      <span>{{ error }}</span>
      <button data-retry type="button" class="btn-secondary" @click="load">重试</button>
    </div>
    <div v-else-if="items.length === 0" class="state-band">没有匹配的内容</div>
    <div v-else class="card-grid">
      <UnifiedCard
        v-for="item in items"
        :key="item.id"
        data-resource-card
        :item="item"
        :options="cardOptions"
        @select="openDetail"
      />
    </div>
    <div v-if="!loading && !error && nextCursor" class="pagination-actions">
      <button
        data-load-more
        type="button"
        class="btn-secondary"
        :disabled="loadingMore"
        @click="loadMore"
      >
        {{ loadingMore ? '加载中...' : '加载更多' }}
      </button>
    </div>

    <AppModal :open="Boolean(selected) && !formOpen" :title="itemTitle(selected)" @close="closeDetail">
      <dl v-if="selected" class="detail-list">
        <template v-for="field in fields" :key="field.key">
          <dt>{{ field.label }}</dt>
          <dd>{{ displayValue(selected[field.key]) }}</dd>
        </template>
      </dl>
      <div v-if="selected" class="modal-actions">
        <button
          v-if="useLabel"
          type="button"
          class="btn-primary"
          @click="emit('use', selected)"
        >
          <i class="ph ph-play" aria-hidden="true"></i>
          {{ useLabel }}
        </button>
        <template v-if="!selected.read_only">
          <button data-edit-resource type="button" class="btn-secondary" @click="openEdit">
            <i class="ph ph-pencil-simple" aria-hidden="true"></i>
            编辑
          </button>
          <button
            v-if="!confirmingDelete"
            data-delete-resource
            type="button"
            class="btn-danger"
            @click="confirmingDelete = true"
          >
            删除
          </button>
          <button
            v-else
            data-confirm-delete
            type="button"
            class="btn-danger"
            @click="removeSelected"
          >
            确认删除
          </button>
        </template>
      </div>
    </AppModal>

    <AppModal :open="formOpen" :title="editingId ? `编辑${title}` : actionLabel" @close="closeForm">
      <form class="resource-form" @submit.prevent="submitForm">
        <label v-for="field in fields" :key="field.key" class="form-field">
          <span>{{ field.label }}</span>
          <textarea
            v-if="field.type === 'textarea'"
            v-model="form[field.key]"
            :name="field.key"
            :required="field.required"
            :placeholder="field.placeholder"
            rows="4"
          ></textarea>
          <select
            v-else-if="field.type === 'select'"
            v-model="form[field.key]"
            :name="field.key"
            :required="field.required"
          >
            <option v-for="option in field.options" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
          <input
            v-else-if="field.type === 'checkbox'"
            v-model="form[field.key]"
            :name="field.key"
            type="checkbox"
          >
          <input
            v-else
            v-model="form[field.key]"
            :name="field.key"
            :type="field.type === 'number' ? 'number' : 'text'"
            :required="field.required"
            :placeholder="field.placeholder"
          >
        </label>
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
import AppModal from './AppModal.vue'
import UnifiedCard from './UnifiedCard.vue'


const props = defineProps({
  resource: { type: String, required: true },
  title: { type: String, required: true },
  subtitle: { type: String, required: true },
  actionLabel: { type: String, required: true },
  searchPlaceholder: { type: String, required: true },
  fields: { type: Array, required: true },
  cardOptions: { type: Object, default: () => ({}) },
  useLabel: { type: String, default: '' },
  service: { type: Object, default: () => resourceApi },
})
const emit = defineEmits(['use'])

const items = ref([])
const loading = ref(true)
const loadingMore = ref(false)
const error = ref('')
const nextCursor = ref(null)
const search = ref('')
const selected = ref(null)
const formOpen = ref(false)
const editingId = ref(null)
const saving = ref(false)
const formError = ref('')
const confirmingDelete = ref(false)
const form = reactive({})
let searchTimer

async function load({ append = false } = {}) {
  if (append) loadingMore.value = true
  else loading.value = true
  error.value = ''
  try {
    const query = {
      search: search.value.trim(),
      limit: 100,
    }
    if (append) query.cursor = nextCursor.value
    const page = await props.service.list(props.resource, query)
    const pageItems = page.items ?? []
    items.value = append ? [...items.value, ...pageItems] : pageItems
    nextCursor.value = page.next_cursor ?? null
  } catch (cause) {
    error.value = cause?.message ?? '加载失败'
  } finally {
    if (append) loadingMore.value = false
    else loading.value = false
  }
}

function loadMore() {
  if (nextCursor.value && !loadingMore.value) load({ append: true })
}

function openCreate() {
  editingId.value = null
  resetForm()
  formOpen.value = true
}

function openDetail(item) {
  selected.value = item
  confirmingDelete.value = false
}

function closeDetail() {
  selected.value = null
  confirmingDelete.value = false
}

function openEdit() {
  editingId.value = selected.value.id
  resetForm(selected.value)
  formOpen.value = true
}

function closeForm() {
  formOpen.value = false
  formError.value = ''
}

function resetForm(source = {}) {
  for (const field of props.fields) {
    const value = source[field.key] ?? field.default ?? (field.type === 'checkbox' ? false : '')
    form[field.key] = field.type === 'list' && Array.isArray(value) ? value.join(', ') : value
  }
  formError.value = ''
}

async function submitForm() {
  const missing = props.fields.find((field) => field.required && !String(form[field.key] ?? '').trim())
  if (missing) {
    formError.value = `${missing.label}不能为空`
    return
  }
  saving.value = true
  formError.value = ''
  const payload = Object.fromEntries(props.fields.map((field) => [field.key, formValue(field)]))
  try {
    if (editingId.value) {
      await props.service.update(props.resource, editingId.value, payload)
    } else {
      await props.service.create(props.resource, payload)
    }
    closeForm()
    closeDetail()
    await load()
  } catch (cause) {
    formError.value = cause?.message ?? '保存失败'
  } finally {
    saving.value = false
  }
}

async function removeSelected() {
  try {
    await props.service.remove(props.resource, selected.value.id)
    closeDetail()
    await load()
  } catch (cause) {
    error.value = cause?.message ?? '删除失败'
    closeDetail()
  }
}

function formValue(field) {
  const value = form[field.key]
  if (field.type === 'list') {
    return String(value)
      .split(',')
      .map((part) => part.trim())
      .filter(Boolean)
  }
  if (field.type === 'number') {
    return Number(value)
  }
  return value
}

function itemTitle(item) {
  return item?.title ?? item?.name ?? '详情'
}

function displayValue(value) {
  if (Array.isArray(value)) return value.join(', ') || '无'
  if (typeof value === 'boolean') return value ? '是' : '否'
  return value || '无'
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
  padding: 28px 0;
  color: #69707c;
  text-align: center;
}

.error-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #b42318;
}

.detail-list {
  display: grid;
  grid-template-columns: minmax(100px, 0.3fr) 1fr;
  gap: 12px 18px;
  margin: 0;
}

.detail-list dt {
  color: #69707c;
  font-size: 0.82rem;
  font-weight: 650;
}

.detail-list dd {
  min-width: 0;
  margin: 0;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.resource-form,
.form-field {
  display: grid;
  gap: 8px;
}

.resource-form {
  gap: 16px;
}

.form-field > span {
  color: #3d4450;
  font-size: 0.82rem;
  font-weight: 650;
}

.form-field input:not([type='checkbox']),
.form-field textarea,
.form-field select {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #d7dce4;
  border-radius: 6px;
  background: white;
  color: #242a33;
  font: inherit;
  letter-spacing: 0;
}

.form-error {
  margin: 0;
  color: #b42318;
  font-size: 0.82rem;
}

.modal-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 22px;
}

.pagination-actions {
  display: flex;
  justify-content: center;
  padding-top: 20px;
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
  color: #394150;
}

.btn-danger {
  border: 1px solid #f2b8b5;
  background: #fff1f0;
  color: #b42318;
}

@media (max-width: 640px) {
  .detail-list {
    grid-template-columns: 1fr;
    gap: 4px;
  }

  .detail-list dd {
    margin-bottom: 12px;
  }
}
</style>
