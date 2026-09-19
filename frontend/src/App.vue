<template>
  <div class="page">
    <header class="topbar">
      <div class="brand">
        <span class="logo">✓</span>
        <div>
          <h1>多模态信息核验系统</h1>
          <p>Multi-Agent · RAG · 多模态事实核验</p>
        </div>
      </div>
      <el-tag :type="mode === 'live' ? 'success' : 'info'" effect="dark">
        {{ mode === 'live' ? 'Live · 已接入真实模型' : 'Mock · 离线演示模式' }}
      </el-tag>
    </header>
    <VerifyView v-model:mode="mode" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import VerifyView from './views/Verify.vue'
import { getHealth } from './api/client'
const mode = ref('mock')

onMounted(async () => {
  try {
    const h = await getHealth()
    if (h?.mock_mode === false) mode.value = 'live'
  } catch (e) {
    // 后端未启动时保持 mock 显示
  }
})
</script>

<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Helvetica Neue', Arial, 'PingFang SC', 'Microsoft YaHei', sans-serif; background: #f5f7fa; color: #1f2d3d; }
.page { max-width: 960px; margin: 0 auto; padding: 0 20px 60px; }
.topbar { display: flex; align-items: center; justify-content: space-between; padding: 20px 0; border-bottom: 1px solid #e4e7ed; margin-bottom: 24px; }
.brand { display: flex; align-items: center; gap: 12px; }
.logo { width: 44px; height: 44px; border-radius: 10px; background: #409eff; color: #fff; display: flex; align-items: center; justify-content: center; font-size: 24px; font-weight: 700; }
.brand h1 { font-size: 20px; }
.brand p { font-size: 12px; color: #909399; margin-top: 2px; }
</style>
