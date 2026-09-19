<template>
  <div>
    <!-- 输入区 -->
    <el-card shadow="never" class="card">
      <template #header>
        <span class="card-title">输入待核验内容</span>
      </template>
      <el-input
        v-model="text"
        type="textarea"
        :rows="5"
        placeholder="粘贴一条有争议的信息、通知或新闻文本…"
      />
      <div class="input-row">
        <el-upload
          v-model:file-list="files"
          :auto-upload="false"
          :limit="3"
          list-type="picture-card"
          accept="image/*"
        >
          <el-icon><Plus /></el-icon>
        </el-upload>
        <el-button
          type="primary"
          size="large"
          :loading="loading"
          :disabled="!hasInput"
          @click="run"
        >
          {{ loading ? '核验中…' : '开始核验' }}
        </el-button>
      </div>
      <p v-if="!hasInput" class="hint">可输入文本，并可上传一张或多张截图/图片（图文混合）。</p>
    </el-card>

    <!-- Agent 执行过程 -->
    <AgentFlow v-if="steps.length" :steps="steps" />

    <!-- 结果 -->
    <template v-if="result">
      <el-alert
        type="warning"
        :closable="false"
        show-icon
        class="disclaimer"
        style="margin-top: 8px"
      >
        {{ disclaimer }}
      </el-alert>

      <div class="summary">
        <el-tag type="success" size="large">支持 {{ counts.support }}</el-tag>
        <el-tag type="danger" size="large">反驳 {{ counts.refute }}</el-tag>
        <el-tag type="info" size="large">证据不足 {{ counts.insufficient }}</el-tag>
        <el-tag v-if="counts.review" type="warning">需人工复核 {{ counts.review }}</el-tag>
      </div>

      <h2 class="section-title">核验结论</h2>
      <div class="verdicts">
        <VerdictCard
          v-for="v in result.verdicts"
          :key="v.claim_id"
          :verdict="v"
          :evidence-map="evidenceMap"
          :assessment-map="assessmentMap"
          :task-id="result.task_id"
        />
      </div>

      <h2 class="section-title">证据与来源</h2>
      <EvidenceList :evidences="result.evidences" :assessment-map="assessmentMap" />
    </template>

    <el-alert
      v-if="error"
      type="error"
      :title="error"
      :closable="false"
      style="margin-top: 16px"
    />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { verifyStreaming } from '../api/client'
import AgentFlow from '../components/AgentFlow.vue'
import VerdictCard from '../components/VerdictCard.vue'
import EvidenceList from '../components/EvidenceList.vue'

const text = ref('')
const files = ref([])
const steps = ref([])
const result = ref(null)
const loading = ref(false)
const error = ref('')
const disclaimer = ref('')

const hasInput = computed(() => text.value.trim().length > 0 || files.value.length > 0)

const counts = computed(() => {
  const c = { support: 0, refute: 0, insufficient: 0, review: 0 }
  for (const v of result.value?.verdicts || []) {
    if (v.verdict === 'support') c.support++
    else if (v.verdict === 'refute') c.refute++
    else c.insufficient++
    if (v.needs_review) c.review++
  }
  return c
})

const evidenceMap = computed(() => {
  const m = {}
  for (const e of result.value?.evidences || []) m[e.evidence_id] = e
  return m
})
const assessmentMap = computed(() => {
  const m = {}
  for (const a of result.value?.assessments || []) m[a.evidence_id] = a
  return m
})

async function run() {
  error.value = ''
  result.value = null
  steps.value = []
  loading.value = true
  const rawFiles = files.value.map((f) => f.raw).filter(Boolean)
  try {
    await verifyStreaming({
      text: text.value,
      files: rawFiles,
      onStep: (s) => steps.value.push(s),
      onResult: (data) => {
        result.value = data
        disclaimer.value = data.disclaimer
      },
      onError: (m) => (error.value = m),
    })
  } catch (e) {
    error.value = '核验失败：' + (e?.message || e)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.card { margin-bottom: 20px; }
.card-title { font-weight: 600; }
.input-row { display: flex; align-items: flex-start; justify-content: space-between; margin-top: 12px; gap: 16px; }
.hint { color: #909399; font-size: 12px; margin-top: 8px; }
.disclaimer { margin-bottom: 16px; }
.summary { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 8px; }
.section-title { margin: 24px 0 12px; font-size: 18px; border-left: 4px solid #409eff; padding-left: 10px; }
.verdicts { display: flex; flex-direction: column; gap: 14px; }
</style>
