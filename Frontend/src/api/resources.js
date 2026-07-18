import { langGraphApi } from './langgraph.js'


export function createResourceApi(graphApi = langGraphApi) {
  return {
    list(resource, query = {}, options = {}) {
      return graphApi.manage({ operation: 'list', resource, query }, options)
    },
    get(resource, resourceId, options = {}) {
      return graphApi.manage({
        operation: 'get',
        resource,
        resource_id: resourceId,
      }, options)
    },
    create(resource, payload, options = {}) {
      return graphApi.manage({ operation: 'create', resource, payload }, options)
    },
    update(resource, resourceId, payload, options = {}) {
      return graphApi.manage({
        operation: 'update',
        resource,
        resource_id: resourceId,
        payload,
      }, options)
    },
    remove(resource, resourceId, options = {}) {
      return graphApi.manage({
        operation: 'delete',
        resource,
        resource_id: resourceId,
      }, options)
    },
    action(resource, resourceId, action, payload = {}, options = {}) {
      const input = {
        operation: 'action',
        resource,
        payload: { action, ...payload },
      }
      if (resourceId) {
        input.resource_id = resourceId
      }
      return graphApi.manage(input, options)
    },
  }
}


export const resourceApi = createResourceApi()
