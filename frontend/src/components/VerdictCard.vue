<template>
  <el-card shadow="never" :class="['verdict-card', verdict.verdict]">
    <div class="head">
      <el-tag :type="tagType" size="large" effect="dark">{{ verdictLabel }}</el-tag>
      <el-tag v-if="verdict.needs_review" type="warning" effect="plain" size="small">需人工复核</el-tag>
      <span class="conf">置信度 {{ Math.round(verdict.confidence * 100) }}%</span>
    </div>

    <div class="claim">{{ verdict.claim_text }}</div>

    <div class="reason" v-if="verdict.reasoning">{{ verdict.reasoning }}</div>

    <div class="refs" v-if="verdict.evidence_refs.length">
      <div class="refs-title">证据依据</div>
      <div v-for="eid in verdict.evidence_refs" :key="eid" class="ref-item">
        <span class="dot" :class="scoreClass"></span>
        <a v-if="evid(eid)?.url" :href="evid(eid).url" target="_blank" rel="noopener">
          {{ evid(eid).source_name || evid(eid).title || eid }}
        </a>
        <span v-else>{{ evid(eid)?.source_name || evid(eid)?.title || eid }}</span>
        <span class="score">可信度 {{ scoreOf(eid) }}</span>
      </div>
    </div>
    <div v-else class="refs-title">无直接证据依据</div>

    <!-- 人工复核入口 -->
    <div class="feedback">
      <el-divider>人工复核</el-divider>
      <el-radio-group v-model="userVerdict" size="small">
        <el-radio-button value="support">支持</el-radio-button>
        <el-radio-button value="refute">反驳</el-radio-button>
        <el-radio-button value="insufficient">证据不足</el-radio-button>
      </el-radio-group>
      <el-input v-model="comment" size="small" placeholder="补充说明（可选）" class="fb-input" />
      <el-button size="small" type="primary" plain :loading="sending" @click="submit">提交复核</el-button>
      <el-tag v-if="sent" type="success" size="small" class="sent-tag">已提交</el-tag>
    </div>
  </el-card>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { submitFeedback } from '../api/client'

const props = defineProps({
  verdict: { type: Object, required: true },
  evidenceMap: { type: Object, default: () => ({}) },
  assessmentMap: { type: Object, default: () => ({}) },
  taskId: { type: String, default: '' },
})

const AGENT_LABELS = {
  support: ['支持', 'success'],
  refute: ['反驳', 'danger'],
  insufficient: ['证据不足', 'info'],
}
const verdictLabel = computed(() => AGENT_LABELS[props.verdict.verdict]?.[0] || props.verdict.verdict)
const tagType = computed(() => AGENT_LABELS[props.verdict.verdict]?.[1] || 'info')

function evid(id) { return props.evidenceMap[id] }
function scoreOf(id) {
  const a = props.assessmentMap[id]
  return a ? a.total_score.toFixed(2) : '—'
}
function scoreClass(id) {
  const a = props.assessmentMap[id]
  if (!a) return 'dot-gray'
  if (a.total_score >= 0.6) return 'dot-green'
  if (a.total_score >= 0.4) return 'dot-yellow'
  return 'dot-red'
}

const userVerdict = ref('')
const comment = ref('')
const sending = ref(false)
const sent = ref(false)
async function submit() {
  if (!userVerdict.value) { ElMessage.warning('请先选择你的判定'); return }
  sending.value = true
  try {
    await submitFeedback(props.taskId, props.verdict.claim_id, userVerdict.value, comment.value)
    sent.value = true
    ElMessage.success('复核反馈已提交')
  } catch (e) {
    ElMessage.error('提交失败：' + (e?.message || e))
  } finally {
    sending.value = false
  }
}
</script>

<style scoped>
.verdict-card { border-left: 5px solid #409eff; }
.verdict-card.support { border-left-color: #67c23a; }
.verdict-card.refute { border-left-color: #f56c6c; }
.verdict-card.insufficient { border-left-color: #909399; }
.head { display: flex; align-items: center; gap: 10px; }
.conf { color: #909399; font-size: 13px; margin-left: auto; }
.claim { font-size: 16px; font-weight: 600; margin: 10px 0 8px; }
.reason { color: #606266; font-size: 14px; }
.refs { margin-top: 12px; }
.refs-title { font-size: 13px; color: #909399; margin-bottom: 6px; }
.ref-item { display: flex; align-items: center; gap: 8px; font-size: 14px; margin-bottom: 6px; }
.ref-item a { color: #409eff; text-decoration: none; }
.dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; }
.dot-green { background: #67c23a; }
.dot-yellow { background: #e6a23c; }
.dot-red { background: #f56c6c; }
.dot-gray { background: #c0c4cc; }
.score { font-size: 12px; color: #909399; }
.feedback { margin-top: 8px; }
.fb-input { margin: 8px 0; }
.sent-tag { margin-left: 8px; }
:deep(.el-divider--horizontal) { margin: 14px 0; }
</style>
