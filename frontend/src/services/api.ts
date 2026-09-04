import axios from 'axios'

const api = axios.create({ baseURL: '/api/v1' })

api.interceptors.request.use((config) => {
  config.headers.set('X-Actor', 'demo-operador')
  return config
})

export default api
