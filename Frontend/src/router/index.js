import { createRouter, createWebHistory } from 'vue-router';

import { isAuthenticated } from '../api/auth.js';

const Auth = () => import('../views/Auth.vue');
const Home = () => import('../views/Home.vue');
const Rules = () => import('../views/Rules.vue');
const Agents = () => import('../views/Agents.vue');
const Knowledge = () => import('../views/Knowledge.vue');
const Plugins = () => import('../views/Plugins.vue');
const MCP = () => import('../views/MCP.vue');
const Prompt = () => import('../views/Prompt.vue');

const routes = [
  { path: '/auth', name: 'Auth', component: Auth, meta: { public: true } },
  { path: '/', name: 'Home', component: Home },
  { path: '/index.html', redirect: '/' }, // Handle legacy link
  { path: '/rules', name: 'Rules', component: Rules },
  { path: '/rules.html', redirect: '/rules' },
  { path: '/agents', name: 'Agents', component: Agents },
  { path: '/agents.html', redirect: '/agents' },
  { path: '/knowledge', name: 'Knowledge', component: Knowledge },
  { path: '/knowledge.html', redirect: '/knowledge' },
  { path: '/plugins', name: 'Plugins', component: Plugins },
  { path: '/plugins.html', redirect: '/plugins' },
  { path: '/mcp', name: 'MCP', component: MCP },
  { path: '/mcp.html', redirect: '/mcp' },
  { path: '/prompt', name: 'Prompt', component: Prompt },
  { path: '/prompt.html', redirect: '/prompt' },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach((to) => {
  if (to.meta.public) {
    return isAuthenticated.value ? '/' : true;
  }
  return isAuthenticated.value ? true : { name: 'Auth', query: { redirect: to.fullPath } };
});

export default router;
