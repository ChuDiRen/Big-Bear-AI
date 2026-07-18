<template>
  <Teleport to="body">
    <div v-if="open" class="modal-backdrop" @click.self="emit('close')">
      <section
        class="modal-panel"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="titleId"
      >
        <header class="modal-header">
          <h2 :id="titleId">{{ title }}</h2>
          <button type="button" class="icon-button" title="关闭" @click="emit('close')">
            <i class="ph ph-x" aria-hidden="true"></i>
          </button>
        </header>
        <div class="modal-body">
          <slot></slot>
        </div>
      </section>
    </div>
  </Teleport>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  open: Boolean,
  title: {
    type: String,
    required: true,
  },
})
const emit = defineEmits(['close'])
const titleId = computed(() => `modal-${props.title.replace(/\W+/g, '-').toLowerCase()}`)
</script>

<style scoped>
.modal-backdrop {
  position: fixed;
  z-index: 100;
  inset: 0;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgb(20 24 32 / 45%);
}

.modal-panel {
  width: min(620px, 100%);
  max-height: min(760px, calc(100vh - 48px));
  overflow: auto;
  border: 1px solid #dfe3ea;
  border-radius: 8px;
  background: white;
  box-shadow: 0 24px 70px rgb(22 31 48 / 24%);
}

.modal-header {
  position: sticky;
  z-index: 1;
  top: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px;
  border-bottom: 1px solid #eaedf2;
  background: white;
}

.modal-header h2 {
  margin: 0;
  font-size: 1.08rem;
  letter-spacing: 0;
}

.modal-body {
  padding: 20px;
}

.icon-button {
  display: inline-grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border: 0;
  border-radius: 6px;
  background: #f2f4f7;
  color: #343a46;
  cursor: pointer;
}
</style>
