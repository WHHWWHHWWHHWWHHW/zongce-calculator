/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 后端地址；留空时用同源（开发时由 Vite 代理 /api 到本机后端） */
  readonly VITE_API_BASE?: string
}
