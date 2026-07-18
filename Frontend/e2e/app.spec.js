import { expect, test } from '@playwright/test'
import { Client } from '@langchain/langgraph-sdk'


const graphClient = new Client({
  apiUrl: process.env.LANGGRAPH_API_URL ?? 'http://127.0.0.1:2025',
})

async function manage(input) {
  const output = await graphClient.runs.wait(null, 'management', {
    input,
    onDisconnect: 'cancel',
  })
  if (!output.ok) throw new Error(`${output.error?.code}: ${output.error?.message}`)
  return output.data
}

async function assertViewport(page) {
  const result = await page.evaluate(() => {
    const root = document.documentElement
    const controls = [...document.querySelectorAll('button, input, textarea, select')]
      .filter((element) => {
        const style = getComputedStyle(element)
        const rect = element.getBoundingClientRect()
        return style.visibility !== 'hidden' && style.display !== 'none' && rect.width > 0
      })
      .map((element) => {
        const rect = element.getBoundingClientRect()
        return {
          label: element.getAttribute('data-testid') || element.getAttribute('name') || element.textContent?.trim(),
          left: rect.left,
          right: rect.right,
        }
      })
      .filter((rect) => rect.left < -1 || rect.right > window.innerWidth + 1)
    return {
      overflow: root.scrollWidth > root.clientWidth + 1,
      controls,
    }
  })
  expect(result, JSON.stringify(result)).toEqual({ overflow: false, controls: [] })
}

async function deleteBySearch(resource, search) {
  const page = await manage({
    operation: 'list',
    resource,
    query: { search, limit: 100 },
  })
  for (const item of page.items) {
    await manage({ operation: 'delete', resource, resource_id: item.id })
  }
}

test('completes every primary frontend workflow', async ({ page }, testInfo) => {
  const consoleErrors = []
  const pageErrors = []
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })
  page.on('pageerror', (error) => pageErrors.push(error.message))

  const suffix = `${testInfo.project.name}-${Date.now()}`
  const ruleTitle = `规则 ${suffix}`
  const promptTitle = `Prompt ${suffix}`
  const agentName = `Agent ${suffix}`
  const documentTitle = `知识 ${suffix}`
  const mcpName = `MCP ${suffix}`
  const projectName = `项目 ${suffix}`

  try {
    await page.goto('/rules')
    await expect(page.getByRole('heading', { name: '规则市场' })).toBeVisible()
    await page.locator('[data-create-resource]').click()
    await page.locator('[name="title"]').fill(ruleTitle)
    await page.locator('[name="definition"]').fill('覆盖边界值和异常输入')
    await page.locator('form').last().getByRole('button', { name: '保存' }).click()
    await expect(page.getByText(ruleTitle, { exact: true })).toBeVisible()
    await assertViewport(page)

    await page.goto('/prompt')
    await page.locator('[data-create-resource]').click()
    await page.locator('[name="title"]').fill(promptTitle)
    await page.locator('[name="template"]').fill('为 {target} 生成测试')
    await page.locator('[name="variables"]').fill('target')
    await page.locator('form').last().getByRole('button', { name: '保存' }).click()
    await expect(page.getByText(promptTitle, { exact: true })).toBeVisible()
    await assertViewport(page)

    await page.goto('/agents')
    await page.locator('[data-create-resource]').click()
    await page.locator('[name="name"]').fill(agentName)
    await page.locator('[name="instructions"]').fill('优先生成可验证的 API 测试')
    await page.locator('form').last().getByRole('button', { name: '保存' }).click()
    await expect(page.getByText(agentName, { exact: true })).toBeVisible()
    await assertViewport(page)

    await page.goto('/knowledge')
    await page.locator('[data-upload-document]').click()
    await page.locator('[data-document-file]').setInputFiles({
      name: `knowledge-${suffix}.txt`,
      mimeType: 'text/plain',
      buffer: Buffer.from('浏览器上传的边界分析知识'),
    })
    await page.locator('[name="title"]').fill(documentTitle)
    await page.locator('[data-upload-form]').getByRole('button', { name: '上传', exact: true }).click()
    await expect(page.getByText(documentTitle, { exact: true })).toBeVisible()
    await assertViewport(page)

    await page.goto('/mcp')
    await page.locator('[data-add-mcp]').click()
    await page.locator('[name="name"]').fill(mcpName)
    await page.locator('[name="command"]').fill('python')
    await page.locator('[name="args"]').fill('server.py')
    await page.locator('[data-mcp-form]').getByRole('button', { name: '保存' }).click()
    await expect(page.getByText(mcpName, { exact: true })).toBeVisible()
    await assertViewport(page)

    await page.goto('/plugins')
    await expect(page.getByText('Mock Server', { exact: true })).toHaveCount(0)
    await expect(page.locator('[data-plugin-card]')).toHaveCount(3)
    await page.locator('[data-plugin-card]').first().click()
    const install = page.locator('[data-install-plugin]')
    if (await install.isVisible()) await install.click()
    await expect(page.locator('[data-configure-plugin]')).toBeVisible()
    await page.locator('[data-uninstall-plugin]').click()
    await page.locator('[data-confirm-uninstall-plugin]').click()
    await expect(page.locator('[data-install-plugin]')).toBeVisible()
    await assertViewport(page)

    await page.goto('/')
    await page.locator('[data-new-project]').click()
    await page.locator('[name="project-name"]').fill(projectName)
    await page.locator('[name="project-description"]').fill('浏览器端到端项目')
    await page.locator('[data-project-form]').getByRole('button', { name: '创建', exact: true }).click()
    await expect(page.getByText(projectName, { exact: true })).toBeVisible()
    await assertViewport(page)

    await page.screenshot({
      path: `../output/playwright/${testInfo.project.name}-home.png`,
      fullPage: true,
    })
    expect(consoleErrors).toEqual([])
    expect(pageErrors).toEqual([])
  } finally {
    await deleteBySearch('project', suffix)
    await deleteBySearch('agent', suffix)
    await deleteBySearch('prompt', suffix)
    await deleteBySearch('rule', suffix)
    const documents = await manage({
      operation: 'list',
      resource: 'document',
      query: { search: suffix, limit: 100 },
    })
    for (const document of documents.items) {
      await manage({ operation: 'delete', resource: 'document', resource_id: document.id })
    }
    const servers = await manage({
      operation: 'list',
      resource: 'mcp',
      query: { search: suffix },
    })
    for (const server of servers.items) {
      await manage({ operation: 'delete', resource: 'mcp', resource_id: server.id })
    }
  }
})
