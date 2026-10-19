<script setup lang="ts">
/**
 * 成绩预估：所有计算由后端 /api/v1/score/preview 完成，本页只收集输入、展示结果（CLAUDE.md §6）。
 */
import { ElMessage } from 'element-plus'
import { reactive, ref } from 'vue'

import { type Schemas, unwrap } from '@/api/client'
import ScoreItems from '@/components/ScoreItems.vue'
import { useAuthStore } from '@/stores/auth'
import { errorMessage } from '@/utils/errors'
import { ruleNames } from '@/utils/rules'

type MoralKey = 'political' | 'morality' | 'discipline' | 'integrity'
const MORAL: { key: MoralKey; label: string; max: number }[] = [
  { key: 'political', label: '政治素养', max: 10 },
  { key: 'morality', label: '品德修养', max: 10 },
  { key: 'discipline', label: '纪律观念', max: 5 },
  { key: 'integrity', label: '诚信评价', max: 5 },
]
const BASIC = [
  { key: 'second_classroom', label: '第二课堂积分' },
  { key: 'public_service', label: '公益劳动次数' },
  { key: 'fitness_test', label: '体质健康测试成绩' },
  { key: 'dorm_check', label: '宿舍检查平均成绩' },
  { key: 'ability', label: '能力分（审核后合计）' },
] as const

const auth = useAuthStore()
const form = reactive({
  gpa: '',
  quality_mode: 'detail' as 'detail' | 'direct',
  quality_direct: '',
  second_classroom: '',
  public_service: '',
  fitness_test: '',
  dorm_check: '',
  ability: '',
})
const moral = reactive(
  Object.fromEntries(MORAL.map((m) => [m.key, { mode: 'score', text: '' }])) as Record<
    MoralKey,
    { mode: 'score' | 'ratings'; text: string }
  >,
)
const result = ref<Schemas['ScoreOut'] | null>(null)
const names = ref<Record<string, string>>({})
const busy = ref(false)

const opt = (value: string) => value.trim() || null

async function calculate(): Promise<void> {
  busy.value = true
  try {
    const moralInputs = Object.fromEntries(
      MORAL.map(({ key }) => {
        const { mode, text } = moral[key]
        if (!text.trim()) return [key, null]
        return [key, mode === 'score' ? { score: text.trim() } : { ratings_text: text }]
      }),
    )
    result.value = unwrap(
      await auth.api.POST('/api/v1/score/preview', {
        body: {
          gpa: opt(form.gpa),
          quality_mode: form.quality_mode,
          quality_direct: opt(form.quality_direct),
          second_classroom: opt(form.second_classroom),
          public_service: opt(form.public_service),
          fitness_test: opt(form.fitness_test),
          dorm_check: opt(form.dorm_check),
          ability: opt(form.ability),
          ...moralInputs,
        },
      }),
    )
    const versions = unwrap(await auth.api.GET('/api/v1/rules'))
    const version = versions.find(
      (v) => v.rule_id === result.value?.rules_id && v.version === result.value?.rules_version,
    )
    if (version) {
      const content = unwrap(
        await auth.api.GET('/api/v1/rules/{version_id}/content', {
          params: { path: { version_id: version.id } },
        }),
      )
      names.value = ruleNames(content.rules)
    }
  } catch (e) {
    ElMessage.error(errorMessage(e))
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h2>成绩预估</h2>
      <span class="muted">按学院现行规则由后端计算，仅供参考，以学院正式核算为准</span>
    </div>
    <el-form label-width="150px" class="form" @submit.prevent="calculate">
      <el-form-item label="平均学分绩点（GPA）">
        <el-input v-model="form.gpa" placeholder="如 3.6524" data-testid="pv-gpa" />
      </el-form-item>
      <el-form-item label="综合素质评价">
        <el-radio-group v-model="form.quality_mode">
          <el-radio value="detail">按细则计算</el-radio>
          <el-radio value="direct">直接输入总分</el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item v-if="form.quality_mode === 'direct'" label="综合素质评价总分">
        <el-input v-model="form.quality_direct" placeholder="0–100" />
      </el-form-item>
      <template v-else>
        <el-divider content-position="left">思想品德行为习惯（满分 30）</el-divider>
        <el-form-item v-for="item in MORAL" :key="item.key" :label="`${item.label}（${item.max}）`">
          <el-radio-group v-model="moral[item.key].mode" size="small" class="mode">
            <el-radio-button value="score">直接得分</el-radio-button>
            <el-radio-button value="ratings">评议名单</el-radio-button>
          </el-radio-group>
          <el-input
            v-model="moral[item.key].text"
            :type="moral[item.key].mode === 'ratings' ? 'textarea' : 'text'"
            :placeholder="
              moral[item.key].mode === 'ratings' ? '全班打分，逗号或空格分隔' : `0–${item.max}`
            "
            :data-testid="`pv-${item.key}`"
          />
        </el-form-item>
        <el-divider content-position="left">综合能力表现（满分 70）</el-divider>
        <el-form-item v-for="item in BASIC" :key="item.key" :label="item.label">
          <el-input v-model="form[item.key]" :data-testid="`pv-${item.key}`" />
        </el-form-item>
      </template>
      <el-button type="primary" native-type="submit" :loading="busy" data-testid="pv-submit">
        计算
      </el-button>
    </el-form>

    <template v-if="result">
      <el-divider />
      <el-descriptions :column="2" border>
        <el-descriptions-item label="综合测评成绩">
          <strong class="score" data-testid="pv-final">{{ result.final_score }}</strong>
        </el-descriptions-item>
        <el-descriptions-item label="综合素质评价">{{ result.quality_total }}</el-descriptions-item>
        <el-descriptions-item label="思想品德">{{
          result.moral_total ?? '—'
        }}</el-descriptions-item>
        <el-descriptions-item label="综合能力">
          {{ result.competence_total ?? '—' }}
        </el-descriptions-item>
      </el-descriptions>
      <h3>计分明细</h3>
      <ScoreItems :items="result.items" :names="names" />
    </template>
  </div>
</template>

<style scoped>
.form {
  max-width: 640px;
}

.mode {
  margin-bottom: 6px;
  width: 100%;
}
</style>
