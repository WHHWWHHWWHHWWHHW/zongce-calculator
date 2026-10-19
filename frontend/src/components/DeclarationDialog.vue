<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, reactive, ref, watch } from 'vue'

import { unwrap } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { type Catalog, type Declaration, findItem, groupedItems } from '@/utils/catalog'
import { errorMessage } from '@/utils/errors'

const props = defineProps<{
  catalog: Catalog | null
  yearId: number
  /** 为空时新建，否则修改 */
  declaration: Declaration | null
}>()
const visible = defineModel<boolean>({ required: true })
const emit = defineEmits<{ saved: [declaration: Declaration] }>()

const auth = useAuthStore()
const busy = ref(false)
const form = reactive({
  catalog_code: '',
  option_code: '' as string,
  title: '',
  description: '',
  team_size: undefined as number | undefined,
  team_position: undefined as number | undefined,
  concurrent_rank: undefined as number | undefined,
  quantity: undefined as number | undefined,
  claimed_score: '',
})

const item = computed(() => findItem(props.catalog, form.catalog_code))
const groups = computed(() => groupedItems(props.catalog))
const editing = computed(() => props.declaration !== null)

watch(visible, (open) => {
  if (!open) return
  const d = props.declaration
  Object.assign(form, {
    catalog_code: d?.catalog_code ?? '',
    option_code: d?.option_code ?? '',
    title: d?.title ?? '',
    description: d?.description ?? '',
    team_size: d?.team_size ?? undefined,
    team_position: d?.team_position ?? undefined,
    concurrent_rank: d?.concurrent_rank ?? undefined,
    quantity: d?.quantity ?? undefined,
    claimed_score: d?.claimed_score ?? '',
  })
})

function onItemChange(): void {
  form.option_code = ''
  form.team_size = form.team_position = form.concurrent_rank = form.quantity = undefined
}

function payload() {
  const it = item.value
  return {
    option_code: it?.scoring === 'fixed' ? form.option_code || null : null,
    title: form.title,
    description: form.description,
    team_size: it?.team ? (form.team_size ?? null) : null,
    team_position: it?.team ? (form.team_position ?? null) : null,
    concurrent_rank: it?.concurrent ? (form.concurrent_rank ?? null) : null,
    quantity: it?.scoring === 'per_unit' ? (form.quantity ?? null) : null,
    claimed_score: form.claimed_score.trim() || null,
  }
}

async function save(): Promise<void> {
  if (!form.catalog_code || !form.title.trim()) {
    ElMessage.warning('请选择申报项目并填写标题')
    return
  }
  busy.value = true
  try {
    const result = props.declaration
      ? unwrap(
          await auth.api.PATCH('/api/v1/declarations/{declaration_id}', {
            params: { path: { declaration_id: props.declaration.id } },
            body: payload(),
          }),
        )
      : unwrap(
          await auth.api.POST('/api/v1/declarations', {
            body: { year_id: props.yearId, catalog_code: form.catalog_code, ...payload() },
          }),
        )
    ElMessage.success(
      result.suggested_score
        ? `已保存，建议分 ${result.suggested_score}`
        : '已保存（该项目由审核人给分）',
    )
    emit('saved', result)
    visible.value = false
  } catch (e) {
    ElMessage.error(errorMessage(e))
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <el-dialog
    v-model="visible"
    :title="editing ? '修改申报' : '新建申报'"
    width="640px"
    destroy-on-close
  >
    <el-form label-width="110px" @submit.prevent="save">
      <el-form-item label="申报项目" required>
        <el-select
          v-model="form.catalog_code"
          filterable
          placeholder="选择项目"
          :disabled="editing"
          style="width: 100%"
          data-testid="decl-item"
          @change="onItemChange"
        >
          <el-option-group v-for="group in groups" :key="group.group" :label="group.group">
            <el-option v-for="it in group.items" :key="it.code" :value="it.code" :label="it.name" />
          </el-option-group>
        </el-select>
      </el-form-item>
      <el-alert v-if="item" type="info" :closable="false" class="hint">
        <template #title>
          <span v-if="item.notes">{{ item.notes }}</span>
          <span class="muted">依据：{{ item.source }}</span>
        </template>
      </el-alert>
      <el-form-item v-if="item?.scoring === 'fixed'" label="级别 / 奖项" required>
        <el-select
          v-model="form.option_code"
          placeholder="选择级别或奖项"
          style="width: 100%"
          data-testid="decl-option"
        >
          <el-option
            v-for="option in item.options"
            :key="option.code"
            :value="option.code"
            :label="`${option.name}（${option.score} 分）`"
          />
        </el-select>
      </el-form-item>
      <template v-if="item?.team">
        <el-form-item label="完成总人数">
          <el-input-number v-model="form.team_size" :min="1" :max="100" />
        </el-form-item>
        <el-form-item label="本人位次">
          <el-input-number v-model="form.team_position" :min="1" :max="100" />
          <span class="muted">多人项目按位次递减分配，单人项目可不填</span>
        </el-form-item>
      </template>
      <el-form-item v-if="item?.concurrent" label="职务高低排序">
        <el-input-number v-model="form.concurrent_rank" :min="1" :max="4" />
        <span class="muted">兼任多个职务时，最高的填 1，依次类推</span>
      </el-form-item>
      <el-form-item v-if="item?.scoring === 'per_unit'" :label="`数量`" required>
        <el-input-number v-model="form.quantity" :min="1" :max="1000" />
        <span class="muted">{{ item.unit_name }}</span>
      </el-form-item>
      <el-form-item label="标题" required>
        <el-input
          v-model="form.title"
          maxlength="200"
          placeholder="如：第十六届蓝桥杯省赛二等奖"
          data-testid="decl-title"
        />
      </el-form-item>
      <el-form-item label="说明">
        <el-input v-model="form.description" type="textarea" :rows="3" maxlength="5000" />
      </el-form-item>
      <el-form-item :label="item?.scoring === 'manual' ? '申报分（必填）' : '申报分（可选）'">
        <el-input
          v-model="form.claimed_score"
          placeholder="如 2 或 2.5"
          style="max-width: 160px"
          data-testid="decl-claimed"
        />
        <span v-if="item?.min_score || item?.max_score" class="muted">
          范围 {{ item?.min_score }}–{{ item?.max_score }}
        </span>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="busy" data-testid="decl-save" @click="save">
        保存草稿
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.hint {
  margin: -6px 0 16px;
}

.hint span {
  display: block;
}

.el-input-number + .muted {
  margin-left: 8px;
}
</style>
