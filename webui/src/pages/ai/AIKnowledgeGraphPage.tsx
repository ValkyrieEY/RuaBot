import { useState, useEffect } from 'react'
import { Database, Search, Network, TrendingUp, Loader2, GitBranch, Sparkles, Filter, Brain } from 'lucide-react'
import axios from 'axios'

const getClient = () => {
  const token = localStorage.getItem('access_token')
  return axios.create({
    baseURL: '/api',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': token ? `Bearer ${token}` : ''
    }
  })
}

interface Triple {
  id: number
  subject: string
  predicate: string
  object: string
  confidence: number
  timestamp: number
  source_chat_id: string
  context?: string
}

interface Entity {
  id: number
  name: string
  entity_type: string
  mention_count: number
  first_seen: number
  last_seen: number
}

interface Stats {
  triples: number
  entities: number
  relationships: number
  avg_confidence: number
  total_extractions?: number
  total_triples_extracted?: number
  avg_triples_per_extraction?: number
}

const entityTypeColors = {
  person: { bg: 'bg-blue-100', text: 'text-blue-700', border: 'border-blue-300' },
  place: { bg: 'bg-green-100', text: 'text-green-700', border: 'border-green-300' },
  organization: { bg: 'bg-purple-100', text: 'text-purple-700', border: 'border-purple-300' },
  thing: { bg: 'bg-orange-100', text: 'text-orange-700', border: 'border-orange-300' },
  concept: { bg: 'bg-pink-100', text: 'text-pink-700', border: 'border-pink-300' },
  unknown: { bg: 'bg-gray-100', text: 'text-gray-700', border: 'border-gray-300' }
}

export default function AIKnowledgeGraphPage() {
  const [activeTab, setActiveTab] = useState<'stats' | 'triples' | 'entities' | 'query'>('stats')
  const [loading, setLoading] = useState(false)
  const [stats, setStats] = useState<Stats | null>(null)
  
  // Triples
  const [triples, setTriples] = useState<Triple[]>([])
  const [triplesTotal, setTriplesTotal] = useState(0)
  const [triplesPage, setTriplesPage] = useState(1)
  const [triplesFilter, setTriplesFilter] = useState({ subject: '', predicate: '', object: '' })
  const [showFilters, setShowFilters] = useState(false)
  
  // Entities
  const [entities, setEntities] = useState<Entity[]>([])
  const [entitiesTotal, setEntitiesTotal] = useState(0)
  const [entitiesPage, setEntitiesPage] = useState(1)
  const [entityTypeFilter, setEntityTypeFilter] = useState('')
  
  // Query
  const [queryText, setQueryText] = useState('')
  const [queryResults, setQueryResults] = useState<Triple[]>([])
  const [querying, setQuerying] = useState(false)
  
  const pageSize = 50

  useEffect(() => {
    loadStats()
  }, [])

  useEffect(() => {
    if (activeTab === 'triples') {
      loadTriples()
    } else if (activeTab === 'entities') {
      loadEntities()
    }
  }, [activeTab, triplesPage, entitiesPage, triplesFilter, entityTypeFilter])

  const loadStats = async () => {
    try {
      const response = await getClient().get('/ai/knowledge/stats')
      setStats(response.data)
    } catch (error) {
      console.error('Failed to load stats:', error)
    }
  }

  const loadTriples = async () => {
    setLoading(true)
    try {
      const params: any = {
        limit: pageSize,
        offset: (triplesPage - 1) * pageSize
      }
      
      if (triplesFilter.subject) params.subject = triplesFilter.subject
      if (triplesFilter.predicate) params.predicate = triplesFilter.predicate
      if (triplesFilter.object) params.obj = triplesFilter.object
      
      const response = await getClient().get('/ai/knowledge/triples', { params })
      setTriples(response.data.items || [])
      setTriplesTotal(response.data.total || 0)
    } catch (error) {
      console.error('Failed to load triples:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadEntities = async () => {
    setLoading(true)
    try {
      const params: any = {
        limit: pageSize,
        offset: (entitiesPage - 1) * pageSize
      }
      
      if (entityTypeFilter) params.entity_type = entityTypeFilter
      
      const response = await getClient().get('/ai/knowledge/entities', { params })
      setEntities(response.data.items || [])
      setEntitiesTotal(response.data.total || 0)
    } catch (error) {
      console.error('Failed to load entities:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleQuery = async () => {
    if (!queryText.trim()) return
    
    setQuerying(true)
    try {
      const response = await getClient().post('/ai/knowledge/query', { 
        query: queryText, 
        limit: 20 
      })
      setQueryResults(response.data.results || [])
    } catch (error) {
      console.error('Failed to query knowledge:', error)
    } finally {
      setQuerying(false)
    }
  }

  const formatDate = (timestamp: number) => {
    return new Date(timestamp * 1000).toLocaleString('zh-CN')
  }

  const renderPagination = (page: number, total: number, setPage: (p: number) => void) => {
    const totalPages = Math.ceil(total / pageSize)
    if (totalPages <= 1) return null

    return (
      <div className="flex items-center justify-between mt-6 pt-4 border-t border-gray-200">
        <div className="text-sm text-gray-600">
          共 <span className="font-semibold text-gray-900">{total}</span> 条记录，
          第 <span className="font-semibold text-gray-900">{page}</span> / {totalPages} 页
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setPage(1)}
            disabled={page === 1}
            className="px-3 py-1 border-2 border-gray-300 rounded-lg disabled:opacity-50 hover:bg-gray-50 transition-colors"
          >
            首页
          </button>
          <button
            onClick={() => setPage(Math.max(1, page - 1))}
            disabled={page === 1}
            className="px-3 py-1 border-2 border-gray-300 rounded-lg disabled:opacity-50 hover:bg-gray-50 transition-colors"
          >
            上一页
          </button>
          <button
            onClick={() => setPage(Math.min(totalPages, page + 1))}
            disabled={page === totalPages}
            className="px-3 py-1 border-2 border-gray-300 rounded-lg disabled:opacity-50 hover:bg-gray-50 transition-colors"
          >
            下一页
          </button>
          <button
            onClick={() => setPage(totalPages)}
            disabled={page === totalPages}
            className="px-3 py-1 border-2 border-gray-300 rounded-lg disabled:opacity-50 hover:bg-gray-50 transition-colors"
          >
            末页
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 via-blue-50 to-indigo-50 p-6">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="p-3 bg-gradient-to-br from-purple-500 to-indigo-500 rounded-xl shadow-lg">
            <GitBranch className="w-8 h-8 text-white" />
          </div>
          <div>
            <h1 className="text-4xl font-bold bg-gradient-to-r from-purple-600 to-indigo-600 bg-clip-text text-transparent">
              知识图谱
            </h1>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-white rounded-2xl shadow-xl border-2 border-gray-200 overflow-hidden mb-8">
        <div className="flex border-b-2 border-gray-200">
          {[
            { id: 'stats', label: '统计概览', icon: TrendingUp, color: 'purple' },
            { id: 'triples', label: '知识三元组', icon: Database, color: 'blue' },
            { id: 'entities', label: '实体列表', icon: Network, color: 'green' },
            { id: 'query', label: '智能查询', icon: Search, color: 'indigo' }
          ].map((tab) => {
            const Icon = tab.icon
            const isActive = activeTab === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`
                  flex-1 flex items-center justify-center gap-2 px-6 py-4 font-medium transition-all relative
                  ${isActive 
                    ? `bg-gradient-to-r from-${tab.color}-50 to-${tab.color}-100 text-${tab.color}-700` 
                    : 'text-gray-600 hover:bg-gray-50'
                  }
                `}
              >
                <Icon className={`w-5 h-5 ${isActive ? 'animate-pulse' : ''}`} />
                <span>{tab.label}</span>
                {isActive && (
                  <div className={`absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r from-${tab.color}-500 to-${tab.color}-600`} />
                )}
              </button>
            )
          })}
        </div>

        <div className="p-8">
          {/* Stats Tab */}
          {activeTab === 'stats' && stats && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                <div className="bg-gradient-to-br from-blue-500 to-blue-600 rounded-2xl p-6 text-white shadow-lg hover:shadow-xl transition-shadow">
                  <div className="flex items-center justify-between mb-3">
                    <Database className="w-8 h-8 opacity-80" />
                    <Sparkles className="w-5 h-5 animate-pulse" />
                  </div>
                  <div className="text-4xl font-bold mb-1">{stats.triples.toLocaleString()}</div>
                  <div className="text-sm opacity-90">知识三元组</div>
                  {stats.total_triples_extracted !== undefined && (
                    <div className="text-xs opacity-75 mt-2 pt-2 border-t border-white border-opacity-20">
                      总提取: {stats.total_triples_extracted.toLocaleString()}
                    </div>
                  )}
                </div>

                <div className="bg-gradient-to-br from-green-500 to-green-600 rounded-2xl p-6 text-white shadow-lg hover:shadow-xl transition-shadow">
                  <div className="flex items-center justify-between mb-3">
                    <Network className="w-8 h-8 opacity-80" />
                    <Brain className="w-5 h-5" />
                  </div>
                  <div className="text-4xl font-bold mb-1">{stats.entities.toLocaleString()}</div>
                  <div className="text-sm opacity-90">实体数量</div>
                </div>

                <div className="bg-gradient-to-br from-purple-500 to-purple-600 rounded-2xl p-6 text-white shadow-lg hover:shadow-xl transition-shadow">
                  <div className="flex items-center justify-between mb-3">
                    <GitBranch className="w-8 h-8 opacity-80" />
                  </div>
                  <div className="text-4xl font-bold mb-1">{stats.relationships.toLocaleString()}</div>
                  <div className="text-sm opacity-90">关系类型</div>
                </div>

                <div className="bg-gradient-to-br from-orange-500 to-orange-600 rounded-2xl p-6 text-white shadow-lg hover:shadow-xl transition-shadow">
                  <div className="flex items-center justify-between mb-3">
                    <TrendingUp className="w-8 h-8 opacity-80" />
                  </div>
                  <div className="text-4xl font-bold mb-1">{(stats.avg_confidence * 100).toFixed(1)}%</div>
                  <div className="text-sm opacity-90">平均置信度</div>
                </div>
              </div>

              {stats.total_extractions !== undefined && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="bg-white border-2 border-indigo-200 rounded-2xl p-6 hover:shadow-lg transition-shadow">
                    <div className="text-sm font-medium text-gray-600 mb-2">总提取次数</div>
                    <div className="text-3xl font-bold text-indigo-600">{stats.total_extractions.toLocaleString()}</div>
                  </div>

                  <div className="bg-white border-2 border-pink-200 rounded-2xl p-6 hover:shadow-lg transition-shadow">
                    <div className="text-sm font-medium text-gray-600 mb-2">平均每次提取</div>
                    <div className="text-3xl font-bold text-pink-600">
                      {stats.avg_triples_per_extraction?.toFixed(2) ?? '0'} <span className="text-lg text-gray-500">个三元组</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Triples Tab */}
          {activeTab === 'triples' && (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <h3 className="text-xl font-semibold text-gray-900 flex items-center gap-2">
                  <Database className="w-6 h-6 text-blue-600" />
                  知识三元组列表
                </h3>
                <button
                  onClick={() => setShowFilters(!showFilters)}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg border-2 transition-all ${
                    showFilters 
                      ? 'bg-blue-50 border-blue-500 text-blue-700'
                      : 'bg-white border-gray-300 text-gray-600 hover:border-gray-400'
                  }`}
                >
                  <Filter className="w-4 h-4" />
                  筛选
                </button>
              </div>

              {showFilters && (
                <div className="bg-blue-50 border-2 border-blue-200 rounded-xl p-4">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <input
                      type="text"
                      placeholder="筛选主语..."
                      value={triplesFilter.subject}
                      onChange={(e) => {
                        setTriplesFilter({ ...triplesFilter, subject: e.target.value })
                        setTriplesPage(1)
                      }}
                      className="px-4 py-2 border-2 border-blue-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    />
                    <input
                      type="text"
                      placeholder="筛选谓语/关系..."
                      value={triplesFilter.predicate}
                      onChange={(e) => {
                        setTriplesFilter({ ...triplesFilter, predicate: e.target.value })
                        setTriplesPage(1)
                      }}
                      className="px-4 py-2 border-2 border-blue-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    />
                    <input
                      type="text"
                      placeholder="筛选宾语..."
                      value={triplesFilter.object}
                      onChange={(e) => {
                        setTriplesFilter({ ...triplesFilter, object: e.target.value })
                        setTriplesPage(1)
                      }}
                      className="px-4 py-2 border-2 border-blue-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    />
                  </div>
                </div>
              )}

              {loading ? (
                <div className="flex items-center justify-center py-16">
                  <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
                </div>
              ) : triples.length === 0 ? (
                <div className="text-center py-16">
                  <Database className="w-16 h-16 mx-auto mb-4 text-gray-300" />
                  <p className="text-gray-500 text-lg">暂无知识三元组</p>
                  <p className="text-gray-400 text-sm mt-2">系统正在从对话中提取知识...</p>
                </div>
              ) : (
                <>
                  <div className="space-y-3">
                    {triples.map((triple) => (
                      <div key={triple.id} className="bg-white border-2 border-gray-200 rounded-xl p-5 hover:shadow-lg hover:border-blue-300 transition-all">
                        <div className="flex items-center gap-3 mb-3">
                          <span className="px-4 py-2 bg-gradient-to-r from-blue-100 to-blue-200 text-blue-900 font-semibold rounded-lg">
                            {triple.subject}
                          </span>
                          <span className="px-3 py-1 bg-purple-100 text-purple-700 text-sm font-medium rounded-lg">
                            {triple.predicate}
                          </span>
                          <span className="px-4 py-2 bg-gradient-to-r from-green-100 to-green-200 text-green-900 font-semibold rounded-lg">
                            {triple.object}
                          </span>
                          <div className="ml-auto flex items-center gap-2">
                            <div className="text-xs text-gray-500">置信度</div>
                            <div className="px-3 py-1 bg-orange-100 text-orange-700 font-bold rounded-lg">
                              {(triple.confidence * 100).toFixed(0)}%
                            </div>
                          </div>
                        </div>
                        {triple.context && (
                          <div className="text-sm text-gray-600 bg-gray-50 p-3 rounded-lg mb-2">
                            {triple.context}
                          </div>
                        )}
                        <div className="flex items-center gap-4 text-xs text-gray-500">
                          <span>来源: {triple.source_chat_id}</span>
                          <span>•</span>
                          <span>{formatDate(triple.timestamp)}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                  {renderPagination(triplesPage, triplesTotal, setTriplesPage)}
                </>
              )}
            </div>
          )}

          {/* Entities Tab */}
          {activeTab === 'entities' && (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <h3 className="text-xl font-semibold text-gray-900 flex items-center gap-2">
                  <Network className="w-6 h-6 text-green-600" />
                  实体列表
                </h3>
              </div>

              <div className="bg-green-50 border-2 border-green-200 rounded-xl p-4">
                <input
                  type="text"
                  placeholder="筛选实体类型 (person/place/organization/thing/concept)..."
                  value={entityTypeFilter}
                  onChange={(e) => {
                    setEntityTypeFilter(e.target.value)
                    setEntitiesPage(1)
                  }}
                  className="px-4 py-2 border-2 border-green-300 rounded-lg w-full focus:ring-2 focus:ring-green-500 focus:border-green-500"
                />
              </div>

              {loading ? (
                <div className="flex items-center justify-center py-16">
                  <Loader2 className="w-8 h-8 animate-spin text-green-500" />
                </div>
              ) : entities.length === 0 ? (
                <div className="text-center py-16">
                  <Network className="w-16 h-16 mx-auto mb-4 text-gray-300" />
                  <p className="text-gray-500 text-lg">暂无实体</p>
                </div>
              ) : (
                <>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {entities.map((entity) => {
                      const typeColor = entityTypeColors[entity.entity_type as keyof typeof entityTypeColors] || entityTypeColors.unknown
                      return (
                        <div key={entity.id} className="bg-white border-2 border-gray-200 rounded-xl p-5 hover:shadow-lg hover:border-green-300 transition-all">
                          <div className="flex items-start justify-between mb-3">
                            <div>
                              <div className="text-lg font-bold text-gray-900 mb-2">{entity.name}</div>
                              <span className={`px-3 py-1 text-xs font-medium rounded-lg border ${typeColor.bg} ${typeColor.text} ${typeColor.border}`}>
                                {entity.entity_type || 'unknown'}
                              </span>
                            </div>
                            <div className="text-right">
                              <div className="text-2xl font-bold text-green-600">{entity.mention_count}</div>
                              <div className="text-xs text-gray-500">提及次数</div>
                            </div>
                          </div>
                          <div className="text-xs text-gray-500 space-y-1 pt-3 border-t border-gray-200">
                            <div>首次: {formatDate(entity.first_seen)}</div>
                            <div>最近: {formatDate(entity.last_seen)}</div>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                  {renderPagination(entitiesPage, entitiesTotal, setEntitiesPage)}
                </>
              )}
            </div>
          )}

          {/* Query Tab */}
          {activeTab === 'query' && (
            <div className="space-y-6">
              <div className="flex gap-3">
                <input
                  type="text"
                  placeholder="输入自然语言查询..."
                  value={queryText}
                  onChange={(e) => setQueryText(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleQuery()}
                  className="flex-1 px-6 py-3 border-2 border-gray-300 rounded-xl text-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                />
                <button
                  onClick={handleQuery}
                  disabled={querying || !queryText.trim()}
                  className="px-8 py-3 bg-gradient-to-r from-indigo-500 to-purple-500 text-white font-medium rounded-xl hover:from-indigo-600 hover:to-purple-600 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 shadow-lg transition-all"
                >
                  {querying ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      查询中...
                    </>
                  ) : (
                    <>
                      <Search className="w-5 h-5" />
                      查询
                    </>
                  )}
                </button>
              </div>

              {queryResults.length > 0 && (
                <div className="space-y-4">
                  <div className="text-sm text-gray-600 bg-white rounded-lg px-4 py-2 border-2 border-gray-200">
                    找到 <span className="font-bold text-indigo-600">{queryResults.length}</span> 条相关知识
                  </div>
                  <div className="space-y-3">
                    {queryResults.map((triple, idx) => (
                      <div key={idx} className="bg-white border-2 border-gray-200 rounded-xl p-5 hover:shadow-lg hover:border-indigo-300 transition-all">
                        <div className="flex items-center gap-3 mb-2">
                          <span className="px-4 py-2 bg-blue-100 text-blue-900 font-semibold rounded-lg">
                            {triple.subject}
                          </span>
                          <span className="px-3 py-1 bg-purple-100 text-purple-700 text-sm font-medium rounded-lg">
                            {triple.predicate}
                          </span>
                          <span className="px-4 py-2 bg-green-100 text-green-900 font-semibold rounded-lg">
                            {triple.object}
                          </span>
                          <div className="ml-auto px-3 py-1 bg-orange-100 text-orange-700 font-bold rounded-lg text-sm">
                            {(triple.confidence * 100).toFixed(0)}%
                          </div>
                        </div>
                        {triple.context && (
                          <div className="text-sm text-gray-600 bg-gray-50 p-3 rounded-lg">
                            {triple.context}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {queryResults.length === 0 && queryText && !querying && (
                <div className="text-center py-12">
                  <Search className="w-16 h-16 mx-auto mb-4 text-gray-300" />
                  <p className="text-gray-500 text-lg">未找到相关结果</p>
                  <p className="text-gray-400 text-sm mt-2">尝试使用不同的关键词或更具体的查询</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
