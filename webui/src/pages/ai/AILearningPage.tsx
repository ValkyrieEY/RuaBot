import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Database, TrendingUp, MessageCircle, Users, Settings, Moon, Search, Loader2, Trash2 } from 'lucide-react';

// Get axios instance with authentication
const getClient = () => {
  const token = localStorage.getItem('access_token');
  return axios.create({
    baseURL: '/api',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': token ? `Bearer ${token}` : ''
    }
  });
};

interface Expression {
  id: number;
  situation: string;
  style: string;
  chat_id: string;
  count: number;
  checked: boolean;
  rejected: boolean;
  created_at: string;
  updated_at: string;
}

interface Jargon {
  id: number;
  content: string;
  meaning: string | null;
  chat_id: string;
  count: number;
  is_jargon: boolean | null;
  is_complete: boolean;
  created_at: string;
  updated_at: string;
}

interface ChatHistory {
  id: number;
  chat_id: string;
  theme: string;
  summary: string;
  start_time: number;
  end_time: number;
  count: number;
  created_at: string;
}

interface MessageRecord {
  id: number;
  message_id: string;
  chat_id: string;
  plain_text: string;
  user_id: string;
  user_nickname: string;
  time: number;
  is_bot_message: boolean;
}

interface PersonInfo {
  id: number;
  person_id: string;
  person_name: string | null;
  nickname: string | null;
  is_known: boolean;
  memory_points: any;
  created_at: string;
}

interface GroupInfo {
  id: number;
  group_id: string;
  group_name: string | null;
  group_impression: string | null;
  topic: string | null;
  member_count: number;
  created_at: string;
}

interface Sticker {
  id: number;
  sticker_type: string;
  sticker_id: string | null;
  sticker_url: string | null;
  sticker_file: string | null;
  situation: string | null;
  emotion: string | null;
  meaning: string | null;
  chat_id: string;
  count: number;
  checked: boolean;
  rejected: boolean;
  created_at: string;
  last_active_time: number;
}

interface Stats {
  expressions_count: number;
  jargons_count: number;
  chat_history_count: number;
  message_records_count: number;
  persons_count: number;
  groups_count: number;
  known_persons_count: number;
  stickers_count: number;
}

const AILearningPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [confirmInput, setConfirmInput] = useState('');
  const [clearingData, setClearingData] = useState(false);
  
  // Expressions
  const [expressions, setExpressions] = useState<Expression[]>([]);
  const [expressionsTotal, setExpressionsTotal] = useState(0);
  const [expressionsPage, setExpressionsPage] = useState(1);
  const [expressionsFilter, setExpressionsFilter] = useState('');
  
  // Jargons
  const [jargons, setJargons] = useState<Jargon[]>([]);
  const [jargonsTotal, setJargonsTotal] = useState(0);
  const [jargonsPage, setJargonsPage] = useState(1);
  const [jargonsFilter, setJargonsFilter] = useState('');
  
  // Chat History
  const [chatHistory, setChatHistory] = useState<ChatHistory[]>([]);
  const [chatHistoryTotal, setChatHistoryTotal] = useState(0);
  const [chatHistoryPage, setChatHistoryPage] = useState(1);
  const [chatHistoryFilter, setChatHistoryFilter] = useState('');
  
  // Message Records
  const [messageRecords, setMessageRecords] = useState<MessageRecord[]>([]);
  const [messageRecordsTotal, setMessageRecordsTotal] = useState(0);
  const [messageRecordsPage, setMessageRecordsPage] = useState(1);
  const [messageRecordsFilter, setMessageRecordsFilter] = useState('');
  
  // Persons
  const [persons, setPersons] = useState<PersonInfo[]>([]);
  const [personsTotal, setPersonsTotal] = useState(0);
  const [personsPage, setPersonsPage] = useState(1);
  
  // Groups
  const [groups, setGroups] = useState<GroupInfo[]>([]);
  const [groupsTotal, setGroupsTotal] = useState(0);
  const [groupsPage, setGroupsPage] = useState(1);

  // Stickers
  const [stickers, setStickers] = useState<Sticker[]>([]);
  const [stickersTotal, setStickersTotal] = useState(0);
  const [stickersPage, setStickersPage] = useState(1);
  const [stickersFilter, setStickersFilter] = useState('');
  
  // Learning Config
  const [learningConfig, setLearningConfig] = useState<any>(null);
  const [savingConfig, setSavingConfig] = useState(false);
  
  // Maintenance Stats
  const [maintenanceStats, setMaintenanceStats] = useState<any>({
    dream: null,
    check: null,
    reflect: null
  });
  
  // Knowledge Graph
  const [kgStats, setKgStats] = useState<any>(null);
  const [kgTriples, setKgTriples] = useState<any[]>([]);
  const [kgQueryText, setKgQueryText] = useState('');
  const [kgQueryResults, setKgQueryResults] = useState<any[]>([]);
  const [kgQuerying, setKgQuerying] = useState(false);
  const [kgActiveSubTab, setKgActiveSubTab] = useState<'triples' | 'query'>('triples');
  
  // HeartFlow
  const [heartflowChats, setHeartflowChats] = useState<any[]>([]);
  const [selectedHeartflowChat, setSelectedHeartflowChat] = useState<any>(null);

  const pageSize = 20;

  useEffect(() => {
    loadStats();
    loadLearningConfig();
  }, []);

  useEffect(() => {
    if (activeTab === 7) {
      loadMaintenanceStats();
      const interval = setInterval(loadMaintenanceStats, 30000); // 每30秒刷新
      return () => clearInterval(interval);
    } else if (activeTab === 8) {
      loadKnowledgeGraphData();
      const interval = setInterval(loadKnowledgeGraphData, 30000);
      return () => clearInterval(interval);
    } else if (activeTab === 9) {
      loadHeartflowData();
      const interval = setInterval(loadHeartflowData, 5000); // 每5秒刷新
      return () => clearInterval(interval);
    }
  }, [activeTab]);

  useEffect(() => {
    if (activeTab === 0) loadExpressions();
    else if (activeTab === 1) loadJargons();
    else if (activeTab === 2) loadChatHistory();
    else if (activeTab === 3) loadMessageRecords();
    else if (activeTab === 4) loadPersons();
    else if (activeTab === 5) loadGroups();
    else if (activeTab === 6) loadStickers();
    else if (activeTab === 7) loadMaintenanceStats();
    else if (activeTab === 8) loadKnowledgeGraphData();
    else if (activeTab === 9) loadHeartflowData();
    else if (activeTab === 10) loadLearningConfig();
  }, [activeTab, expressionsPage, expressionsFilter, jargonsPage, jargonsFilter, 
      chatHistoryPage, chatHistoryFilter, messageRecordsPage, messageRecordsFilter,
      personsPage, groupsPage, stickersPage, stickersFilter]);

  const loadStats = async () => {
    try {
      const response = await getClient().get('/ai/learning/stats');
      setStats(response.data);
    } catch (err: any) {
      console.error('Failed to load stats:', err);
    }
  };

  const loadExpressions = async () => {
    setLoading(true);
    setError(null);
    try {
      const params: any = {
        limit: pageSize,
        offset: (expressionsPage - 1) * pageSize,
      };
      if (expressionsFilter) params.chat_id = expressionsFilter;
      
      const response = await getClient().get('/ai/learning/expressions', { params });
      setExpressions(response.data.items);
      setExpressionsTotal(response.data.total);
    } catch (err: any) {
      console.error('Failed to load expressions:', err);
      setError(err.response?.data?.detail || '加载失败');
    } finally {
      setLoading(false);
    }
  };

  const loadJargons = async () => {
    setLoading(true);
    setError(null);
    try {
      const params: any = {
        limit: pageSize,
        offset: (jargonsPage - 1) * pageSize,
      };
      if (jargonsFilter) params.chat_id = jargonsFilter;
      
      const response = await getClient().get('/ai/learning/jargons', { params });
      setJargons(response.data.items);
      setJargonsTotal(response.data.total);
    } catch (err: any) {
      setError(err.response?.data?.detail || '加载失败');
    } finally {
      setLoading(false);
    }
  };

  const loadChatHistory = async () => {
    setLoading(true);
    setError(null);
    try {
      const params: any = {
        limit: pageSize,
        offset: (chatHistoryPage - 1) * pageSize,
      };
      if (chatHistoryFilter) params.chat_id = chatHistoryFilter;
      
      const response = await getClient().get('/ai/learning/chat-history', { params });
      setChatHistory(response.data.items || []);
      setChatHistoryTotal(response.data.total || 0);
    } catch (err: any) {
      console.error('Failed to load chat history:', err);
      setError(err.response?.data?.detail || '加载失败');
    } finally {
      setLoading(false);
    }
  };

  const loadMessageRecords = async () => {
    setLoading(true);
    setError(null);
    try {
      const params: any = {
        limit: pageSize,
        offset: (messageRecordsPage - 1) * pageSize,
      };
      if (messageRecordsFilter) params.chat_id = messageRecordsFilter;
      
      const response = await getClient().get('/ai/learning/message-records', { params });
      setMessageRecords(response.data.items);
      setMessageRecordsTotal(response.data.total);
    } catch (err: any) {
      setError(err.response?.data?.detail || '加载失败');
    } finally {
      setLoading(false);
    }
  };

  const loadPersons = async () => {
    setLoading(true);
    setError(null);
    try {
      const params: any = {
        limit: pageSize,
        offset: (personsPage - 1) * pageSize,
      };
      
      const response = await getClient().get('/ai/learning/persons', { params });
      setPersons(response.data.items);
      setPersonsTotal(response.data.total);
    } catch (err: any) {
      setError(err.response?.data?.detail || '加载失败');
    } finally {
      setLoading(false);
    }
  };

  const loadGroups = async () => {
    setLoading(true);
    setError(null);
    try {
      const params: any = {
        limit: pageSize,
        offset: (groupsPage - 1) * pageSize,
      };
      
      const response = await getClient().get('/ai/learning/groups', { params });
      setGroups(response.data.items || []);
      setGroupsTotal(response.data.total || 0);
    } catch (err: any) {
      console.error('Failed to load groups:', err);
      setError(err.response?.data?.detail || '加载失败');
    } finally {
      setLoading(false);
    }
  };

  const loadStickers = async () => {
    setLoading(true);
    setError(null);
    try {
      const params: any = {
        limit: pageSize,
        offset: (stickersPage - 1) * pageSize,
      };
      if (stickersFilter) params.chat_id = stickersFilter;
      
      const response = await getClient().get('/ai/learning/stickers', { params });
      setStickers(response.data.items);
      setStickersTotal(response.data.total);
    } catch (err: any) {
      console.error('Failed to load stickers:', err);
      setError(err.response?.data?.detail || '加载失败');
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString('zh-CN');
  };

  const formatTimestamp = (timestamp: number) => {
    return new Date(timestamp * 1000).toLocaleString('zh-CN');
  };

  const loadLearningConfig = async () => {
    try {
      const response = await getClient().get('/ai/learning/config', {
        params: { config_type: 'global' }
      });
      setLearningConfig(response.data);
    } catch (error) {
      console.error('Failed to load learning config:', error);
      setError('加载配置失败');
    }
  };

  const saveLearningConfig = async () => {
    setSavingConfig(true);
    try {
      await getClient().put('/ai/learning/config', learningConfig, {
        params: { config_type: 'global' }
      });
      setError(null);
      alert('配置已保存');
    } catch (error) {
      console.error('Failed to save learning config:', error);
      setError('保存配置失败');
    } finally {
      setSavingConfig(false);
    }
  };

  const loadMaintenanceStats = async () => {
    try {
      const [dreamRes, checkRes, reflectRes] = await Promise.all([
        getClient().get('/ai/maintenance/dream/stats').catch((err) => {
          console.error('Failed to load dream stats:', err);
          return { data: null };
        }),
        getClient().get('/ai/maintenance/expression-check/stats').catch((err) => {
          console.error('Failed to load check stats:', err);
          return { data: null };
        }),
        getClient().get('/ai/maintenance/expression-reflect/stats').catch((err) => {
          console.error('Failed to load reflect stats:', err);
          return { data: null };
        })
      ]);
      setMaintenanceStats({
        dream: dreamRes.data,
        check: checkRes.data,
        reflect: reflectRes.data
      });
    } catch (error) {
      console.error('Failed to load maintenance stats:', error);
    }
  };

  const loadKnowledgeGraphData = async () => {
    try {
      const statsRes = await getClient().get('/ai/knowledge/stats').catch((err) => {
        console.error('Failed to load KG stats:', err);
        return { data: { triples: 0, entities: 0, relationships: 0, avg_confidence: 0.0 } };
      });
      setKgStats(statsRes.data || { triples: 0, entities: 0, relationships: 0, avg_confidence: 0.0 });
      
      const triplesRes = await getClient().get('/ai/knowledge/triples', {
        params: { limit: 20, offset: 0 }
      }).catch((err) => {
        console.error('Failed to load KG triples:', err);
        return { data: { items: [], total: 0 } };
      });
      setKgTriples(triplesRes.data?.items || []);
    } catch (error) {
      console.error('Failed to load knowledge graph data:', error);
      setKgStats({ triples: 0, entities: 0, relationships: 0, avg_confidence: 0.0 });
      setKgTriples([]);
    }
  };

  const loadHeartflowData = async () => {
    try {
      const response = await getClient().get('/ai/heartflow/chats').catch((err) => {
        console.error('Failed to load heartflow chats:', err);
        return { data: { chats: [] } };
      });
      const chats = response.data?.chats || [];
      setHeartflowChats(chats);
    } catch (error) {
      console.error('Failed to load heartflow data:', error);
      setHeartflowChats([]);
    }
  };

  const loadHeartflowChatDetails = async (chatId: string) => {
    try {
      const response = await getClient().get(`/ai/heartflow/stats/${encodeURIComponent(chatId)}`);
      setSelectedHeartflowChat({ chat_id: chatId, ...response.data });
    } catch (error) {
      console.error('Failed to load heartflow chat details:', error);
    }
  };

  const handleKgQuery = async () => {
    if (!kgQueryText.trim()) return;
    
    setKgQuerying(true);
    try {
      const response = await getClient().post('/ai/knowledge/query', {
        query: kgQueryText,
        limit: 20
      });
      setKgQueryResults(response.data.results || []);
    } catch (error: any) {
      console.error('Failed to query knowledge:', error);
      setKgQueryResults([]);
      alert(error.response?.data?.detail || '查询失败，请重试');
    } finally {
      setKgQuerying(false);
    }
  };

  const handleClearAllData = async () => {
    if (confirmInput !== '确认格式化') {
      return;
    }

    setClearingData(true);
    try {
      const response = await getClient().delete('/ai/learning/clear-all');
      
      setExpressions([]);
      setExpressionsTotal(0);
      setJargons([]);
      setJargonsTotal(0);
      setChatHistory([]);
      setChatHistoryTotal(0);
      setMessageRecords([]);
      setMessageRecordsTotal(0);
      setPersons([]);
      setPersonsTotal(0);
      setGroups([]);
      setGroupsTotal(0);
      setStickers([]);
      setStickersTotal(0);
      
      setKgStats(null);
      setKgTriples([]);
      setHeartflowChats([]);
      setSelectedHeartflowChat(null);
      setMaintenanceStats({
        dream: null,
        check: null,
        reflect: null
      });
      
      await loadStats();
      
      if (activeTab === 7) {
        await loadMaintenanceStats();
      } else if (activeTab === 8) {
        await loadKnowledgeGraphData();
      } else if (activeTab === 9) {
        await loadHeartflowData();
      }
      
      setShowConfirmDialog(false);
      setConfirmInput('');
      
      const clearedTables = response.data?.cleared_tables || [];
      alert(`所有学习数据已成功清除！\n\n已清除的表：\n${clearedTables.join('\n')}`);
    } catch (err: any) {
      console.error('Failed to clear data:', err);
      alert(err.response?.data?.detail || '清除失败，请重试');
    } finally {
      setClearingData(false);
    }
  };

  const renderPagination = (page: number, total: number, onChange: (page: number) => void) => {
    const totalPages = Math.ceil(total / pageSize);
    if (totalPages <= 1) return null;

    return (
      <div className="flex justify-center items-center mt-4 space-x-2">
        <button
          onClick={() => onChange(Math.max(1, page - 1))}
          disabled={page === 1}
          className="px-3 py-1 rounded border bg-white disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
        >
          上一页
        </button>
        <span className="px-4 py-1 text-sm text-gray-600">
          第 {page} / {totalPages} 页 (共 {total} 条)
        </span>
        <button
          onClick={() => onChange(Math.min(totalPages, page + 1))}
          disabled={page === totalPages}
          className="px-3 py-1 rounded border bg-white disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
        >
          下一页
        </button>
      </div>
    );
  };

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 py-6 mb-2">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">AI 学习数据</h1>
          <p className="text-sm text-gray-500 mt-1">管理 AI 的学习数据、知识图谱与记忆</p>
        </div>
        <button
          onClick={() => setShowConfirmDialog(true)}
          className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-xl hover:bg-red-700 transition-colors shadow-sm text-sm"
        >
          <Trash2 className="w-4 h-4" />
          格式化数据
        </button>
      </div>

      {/* Confirm Dialog */}
      {showConfirmDialog && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4 backdrop-blur-sm">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4">确认格式化</h2>
            <div className="bg-red-50 p-4 rounded-xl mb-4 border border-red-100">
              <p className="text-red-800 font-bold text-sm mb-2">
                ⚠️ 警告：此操作不可恢复！
              </p>
              <p className="text-red-700 text-sm">
                将永久删除所有 AI 学习到的表达习惯、黑话、记忆、知识图谱等数据。
              </p>
            </div>
            <p className="text-sm text-gray-600 mb-4">
              请输入 "<span className="font-mono font-bold text-gray-900">确认格式化</span>" 以继续：
            </p>
            <input
              type="text"
              value={confirmInput}
              onChange={(e) => setConfirmInput(e.target.value)}
              className="w-full px-4 py-2.5 border border-gray-300 rounded-xl mb-6 focus:ring-2 focus:ring-red-500 focus:border-transparent"
              disabled={clearingData}
            />
            <div className="flex space-x-3">
              <button
                onClick={() => {
                  setShowConfirmDialog(false);
                  setConfirmInput('');
                }}
                className="flex-1 px-4 py-2.5 border border-gray-300 text-gray-700 rounded-xl hover:bg-gray-50 font-medium transition-colors"
                disabled={clearingData}
              >
                取消
              </button>
              <button
                onClick={handleClearAllData}
                disabled={confirmInput !== '确认格式化' || clearingData}
                className="flex-1 px-4 py-2.5 bg-red-600 text-white rounded-xl hover:bg-red-700 disabled:opacity-50 font-medium transition-colors shadow-sm"
              >
                {clearingData ? '清除中...' : '确认删除'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Stats Overview */}
      {stats && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {[
            { label: '表达习惯', value: stats.expressions_count, icon: TrendingUp, color: 'text-blue-600', bg: 'bg-blue-50' },
            { label: '黑话术语', value: stats.jargons_count, icon: Database, color: 'text-green-600', bg: 'bg-green-50' },
            { label: '消息记录', value: stats.message_records_count, icon: MessageCircle, color: 'text-purple-600', bg: 'bg-purple-50' },
            { label: '认识的人', value: `${stats.known_persons_count}/${stats.persons_count}`, icon: Users, color: 'text-orange-600', bg: 'bg-orange-50' }
          ].map((stat, i) => (
            <div key={i} className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm flex items-center justify-between hover:shadow-md transition-shadow">
              <div>
                <p className="text-sm text-gray-500">{stat.label}</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">{stat.value}</p>
              </div>
              <div className={`p-3 rounded-xl ${stat.bg} ${stat.color}`}>
                <stat.icon className="w-6 h-6" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Tabs Navigation */}
      <div className="flex space-x-1 bg-gray-100/50 p-1 rounded-xl mb-6 overflow-x-auto scrollbar-hide border border-gray-200">
        {['表达习惯', '黑话术语', '聊天历史', '消息记录', '用户信息', '群组信息', '表情包', '自动维护', '知识图谱', '对话流', '功能配置'].map((label, index) => (
          <button
            key={index}
            onClick={() => setActiveTab(index)}
            className={`px-4 py-2 text-sm font-medium rounded-lg transition-all whitespace-nowrap ${
              activeTab === index
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-500 hover:text-gray-700 hover:bg-gray-200/50'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="space-y-6">
        {error && (
          <div className="mb-4 p-4 bg-red-50 border border-red-100 rounded-xl flex items-center gap-2 text-red-700 text-sm">
            <span className="w-1.5 h-1.5 rounded-full bg-red-500"></span>
            {error}
          </div>
        )}

        {loading ? (
          <div className="flex justify-center items-center py-20">
            <div className="w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
          </div>
        ) : (
          <>
            {/* Content Renderers */}
            {activeTab === 0 && (
              <>
                <div className="mb-4">
                  <div className="relative max-w-sm">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <input
                      type="text"
                      placeholder="筛选聊天 ID..."
                      value={expressionsFilter}
                      onChange={(e) => {
                        setExpressionsFilter(e.target.value);
                        setExpressionsPage(1);
                      }}
                      className="w-full pl-9 pr-4 py-2.5 bg-white border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent shadow-sm transition-all"
                    />
                  </div>
                </div>
                <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm text-left">
                      <thead className="bg-gray-50 text-gray-500 font-medium">
                        <tr>
                          <th className="px-6 py-3">情境</th>
                          <th className="px-6 py-3">表达方式</th>
                          <th className="px-6 py-3">来源</th>
                          <th className="px-6 py-3">次数</th>
                          <th className="px-6 py-3">状态</th>
                          <th className="px-6 py-3">更新时间</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {expressions.map((expr) => (
                          <tr key={expr.id} className="hover:bg-gray-50/50 transition-colors">
                            <td className="px-6 py-4 text-gray-900 font-medium">{expr.situation}</td>
                            <td className="px-6 py-4 text-gray-700">{expr.style}</td>
                            <td className="px-6 py-4 font-mono text-gray-500 text-xs">{expr.chat_id}</td>
                            <td className="px-6 py-4 text-gray-500">{expr.count}</td>
                            <td className="px-6 py-4">
                              <span className={`px-2.5 py-1 rounded-full text-xs font-medium border ${
                                expr.rejected ? 'bg-red-50 text-red-700 border-red-100' :
                                expr.checked ? 'bg-green-50 text-green-700 border-green-100' :
                                'bg-gray-100 text-gray-600 border-gray-200'
                              }`}>
                                {expr.rejected ? '已拒绝' : expr.checked ? '已检查' : '未检查'}
                              </span>
                            </td>
                            <td className="px-6 py-4 text-gray-500 text-xs">{formatDate(expr.updated_at)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
                {renderPagination(expressionsPage, expressionsTotal, setExpressionsPage)}
              </>
            )}

            {/* Other tabs follow similar pattern of removing outer wrapper and enhancing table style */}
            {/* Jargons Tab */}
            {activeTab === 1 && (
              <>
                <div className="mb-4">
                  <div className="relative max-w-sm">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <input
                      type="text"
                      placeholder="筛选聊天 ID..."
                      value={jargonsFilter}
                      onChange={(e) => {
                        setJargonsFilter(e.target.value);
                        setJargonsPage(1);
                      }}
                      className="w-full pl-9 pr-4 py-2.5 bg-white border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent shadow-sm transition-all"
                    />
                  </div>
                </div>
                <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm text-left">
                      <thead className="bg-gray-50 text-gray-500 font-medium">
                        <tr>
                          <th className="px-6 py-3">黑话</th>
                          <th className="px-6 py-3">含义</th>
                          <th className="px-6 py-3">来源</th>
                          <th className="px-6 py-3">次数</th>
                          <th className="px-6 py-3">状态</th>
                          <th className="px-6 py-3">更新时间</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {jargons.map((jargon) => (
                          <tr key={jargon.id} className="hover:bg-gray-50/50 transition-colors">
                            <td className="px-6 py-4 font-bold text-gray-900">{jargon.content}</td>
                            <td className="px-6 py-4 text-gray-600">{jargon.meaning || '-'}</td>
                            <td className="px-6 py-4 font-mono text-gray-500 text-xs">{jargon.chat_id}</td>
                            <td className="px-6 py-4 text-gray-500">{jargon.count}</td>
                            <td className="px-6 py-4">
                              <span className={`px-2.5 py-1 rounded-full text-xs font-medium border ${
                                jargon.is_complete ? 'bg-green-50 text-green-700 border-green-100' :
                                jargon.is_jargon === true ? 'bg-blue-50 text-blue-700 border-blue-100' :
                                jargon.is_jargon === false ? 'bg-gray-100 text-gray-600 border-gray-200' :
                                'bg-yellow-50 text-yellow-700 border-yellow-100'
                              }`}>
                                {jargon.is_complete ? '已完成' :
                                 jargon.is_jargon === true ? '是黑话' :
                                 jargon.is_jargon === false ? '非黑话' : '待判定'}
                              </span>
                            </td>
                            <td className="px-6 py-4 text-gray-500 text-xs">{formatDate(jargon.updated_at)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
                {renderPagination(jargonsPage, jargonsTotal, setJargonsPage)}
              </>
            )}

            {/* Chat History Tab */}
            {activeTab === 2 && (
              <>
                <div className="mb-4">
                  <div className="relative max-w-sm">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <input
                      type="text"
                      placeholder="筛选聊天 ID..."
                      value={chatHistoryFilter}
                      onChange={(e) => {
                        setChatHistoryFilter(e.target.value);
                        setChatHistoryPage(1);
                      }}
                      className="w-full pl-9 pr-4 py-2.5 bg-white border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent shadow-sm transition-all"
                    />
                  </div>
                </div>
                <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm text-left">
                      <thead className="bg-gray-50 text-gray-500 font-medium">
                        <tr>
                          <th className="px-6 py-3 w-1/4">主题</th>
                          <th className="px-6 py-3 w-1/2">概要</th>
                          <th className="px-6 py-3">来源</th>
                          <th className="px-6 py-3 text-right">检索次数</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {chatHistory.map((hist) => (
                          <tr key={hist.id} className="hover:bg-gray-50/50 transition-colors">
                            <td className="px-6 py-4 font-bold text-gray-900">{hist.theme}</td>
                            <td className="px-6 py-4 text-gray-600 leading-relaxed">{hist.summary.substring(0, 100)}{hist.summary.length > 100 ? '...' : ''}</td>
                            <td className="px-6 py-4 font-mono text-gray-500 text-xs">{hist.chat_id}</td>
                            <td className="px-6 py-4 text-gray-500 text-right">{hist.count}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
                {renderPagination(chatHistoryPage, chatHistoryTotal, setChatHistoryPage)}
              </>
            )}

            {/* Message Records Tab */}
            {activeTab === 3 && (
              <>
                <div className="mb-4">
                  <div className="relative max-w-sm">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <input
                      type="text"
                      placeholder="筛选聊天 ID..."
                      value={messageRecordsFilter}
                      onChange={(e) => {
                        setMessageRecordsFilter(e.target.value);
                        setMessageRecordsPage(1);
                      }}
                      className="w-full pl-9 pr-4 py-2.5 bg-white border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent shadow-sm transition-all"
                    />
                  </div>
                </div>
                <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm text-left">
                      <thead className="bg-gray-50 text-gray-500 font-medium">
                        <tr>
                          <th className="px-6 py-3 w-1/2">内容</th>
                          <th className="px-6 py-3">发送者</th>
                          <th className="px-6 py-3">来源</th>
                          <th className="px-6 py-3">时间</th>
                          <th className="px-6 py-3">类型</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {messageRecords.map((record) => (
                          <tr key={record.id} className="hover:bg-gray-50/50 transition-colors">
                            <td className="px-6 py-4 text-gray-900 break-words max-w-md leading-relaxed">{record.plain_text?.substring(0, 150) || '-'}</td>
                            <td className="px-6 py-4 text-gray-600 font-medium">{record.user_nickname || record.user_id}</td>
                            <td className="px-6 py-4 font-mono text-gray-500 text-xs">{record.chat_id}</td>
                            <td className="px-6 py-4 text-gray-500 text-xs">{formatTimestamp(record.time)}</td>
                            <td className="px-6 py-4">
                              <span className={`px-2.5 py-1 rounded-full text-xs font-medium border ${
                                record.is_bot_message 
                                  ? 'bg-blue-50 text-blue-700 border-blue-100' 
                                  : 'bg-gray-50 text-gray-600 border-gray-200'
                              }`}>
                                {record.is_bot_message ? 'Bot' : 'User'}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
                {renderPagination(messageRecordsPage, messageRecordsTotal, setMessageRecordsPage)}
              </>
            )}

            {/* Persons Tab */}
            {activeTab === 4 && (
              <>
                <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm text-left">
                      <thead className="bg-gray-50 text-gray-500 font-medium">
                        <tr>
                          <th className="px-6 py-3">用户 ID</th>
                          <th className="px-6 py-3">AI 认知名</th>
                          <th className="px-6 py-3">昵称</th>
                          <th className="px-6 py-3">状态</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {persons.map((person) => (
                          <tr key={person.id} className="hover:bg-gray-50/50 transition-colors">
                            <td className="px-6 py-4 font-mono text-gray-900 font-medium">{person.person_id}</td>
                            <td className="px-6 py-4 text-gray-900">{person.person_name || '-'}</td>
                            <td className="px-6 py-4 text-gray-600">{person.nickname || '-'}</td>
                            <td className="px-6 py-4">
                              <span className={`px-2.5 py-1 rounded-full text-xs font-medium border ${
                                person.is_known 
                                  ? 'bg-green-50 text-green-700 border-green-100' 
                                  : 'bg-gray-50 text-gray-500 border-gray-200'
                              }`}>
                                {person.is_known ? '已认识' : '未认识'}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
                {renderPagination(personsPage, personsTotal, setPersonsPage)}
              </>
            )}

            {/* Groups Tab */}
            {activeTab === 5 && (
              <>
                <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm text-left">
                      <thead className="bg-gray-50 text-gray-500 font-medium">
                        <tr>
                          <th className="px-6 py-3">群 ID</th>
                          <th className="px-6 py-3">群名称</th>
                          <th className="px-6 py-3 w-1/3">群印象</th>
                          <th className="px-6 py-3 text-right">成员数</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {groups.map((group) => (
                          <tr key={group.id} className="hover:bg-gray-50/50 transition-colors">
                            <td className="px-6 py-4 font-mono text-gray-900 font-medium">{group.group_id}</td>
                            <td className="px-6 py-4 font-bold text-gray-900">{group.group_name || '-'}</td>
                            <td className="px-6 py-4 text-gray-600">{group.group_impression?.substring(0, 100) || '-'}...</td>
                            <td className="px-6 py-4 text-gray-600 font-mono text-right">{group.member_count}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
                {renderPagination(groupsPage, groupsTotal, setGroupsPage)}
              </>
            )}

            {/* Stickers Tab */}
            {activeTab === 6 && (
              <>
                <div className="mb-4">
                  <div className="relative max-w-sm">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <input
                      type="text"
                      placeholder="筛选聊天 ID..."
                      value={stickersFilter}
                      onChange={(e) => {
                        setStickersFilter(e.target.value);
                        setStickersPage(1);
                      }}
                      className="w-full pl-9 pr-4 py-2.5 bg-white border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent shadow-sm transition-all"
                    />
                  </div>
                </div>
                <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm text-left">
                      <thead className="bg-gray-50 text-gray-500 font-medium">
                        <tr>
                          <th className="px-6 py-3">类型</th>
                          <th className="px-6 py-3">情境/情感</th>
                          <th className="px-6 py-3 w-1/4">含义</th>
                          <th className="px-6 py-3">来源</th>
                          <th className="px-6 py-3">次数</th>
                          <th className="px-6 py-3">状态</th>
                          <th className="px-6 py-3">最后使用</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {stickers.map((sticker) => (
                          <tr key={sticker.id} className="hover:bg-gray-50/50 transition-colors">
                            <td className="px-6 py-4 text-gray-900 font-medium">{sticker.sticker_type}</td>
                            <td className="px-6 py-4">
                              <div className="flex flex-col">
                                <span className="text-gray-900">{sticker.situation || '-'}</span>
                                <span className="text-xs text-gray-500">{sticker.emotion || '-'}</span>
                              </div>
                            </td>
                            <td className="px-6 py-4 text-gray-600 text-xs leading-relaxed" title={sticker.meaning || ''}>
                              {sticker.meaning ? sticker.meaning.substring(0, 50) + '...' : '-'}
                            </td>
                            <td className="px-6 py-4 font-mono text-gray-500 text-xs">{sticker.chat_id}</td>
                            <td className="px-6 py-4 text-gray-500">{sticker.count}</td>
                            <td className="px-6 py-4">
                              <span className={`px-2.5 py-1 rounded-full text-xs font-medium border ${
                                sticker.rejected ? 'bg-red-50 text-red-700 border-red-100' :
                                sticker.checked ? 'bg-green-50 text-green-700 border-green-100' :
                                'bg-gray-100 text-gray-600 border-gray-200'
                              }`}>
                                {sticker.rejected ? '已拒绝' : sticker.checked ? '已检查' : '未检查'}
                              </span>
                            </td>
                            <td className="px-6 py-4 text-gray-500 text-xs font-mono">
                              {sticker.last_active_time ? formatTimestamp(sticker.last_active_time) : '-'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
                {renderPagination(stickersPage, stickersTotal, setStickersPage)}
              </>
            )}

            {/* Maintenance Tab */}
            {activeTab === 7 && (
              <div className="space-y-6">
                <div className="bg-blue-50 border border-blue-100 rounded-xl p-5 flex items-start gap-4">
                  <div className="p-2 bg-blue-100 rounded-lg text-blue-600">
                    <Settings className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="font-bold text-blue-900 text-lg">AI 自动维护系统</h3>
                    <p className="text-blue-700/80 text-sm mt-1">包括梦境系统（自动整理记忆）、表达方式自动检查、表达方式反思等功能</p>
                  </div>
                </div>

                <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {/* Dream System */}
                  <div className="bg-white border border-gray-200 rounded-xl p-6 hover:shadow-md transition-all">
                    <div className="flex items-center gap-3 mb-5 pb-4 border-b border-gray-100">
                      <div className="p-2 bg-indigo-50 rounded-lg text-indigo-600">
                        <Moon className="w-5 h-5" />
                      </div>
                      <h3 className="font-bold text-gray-900 text-lg">Dream 梦境系统</h3>
                    </div>
                    {maintenanceStats.dream ? (
                      <div className="space-y-4">
                        <div className="flex justify-between items-center">
                          <span className="text-gray-500 text-sm">总周期数</span>
                          <span className="font-mono font-bold text-gray-900 text-lg">{maintenanceStats.dream.total_cycles}</span>
                        </div>
                        <div className="flex justify-between items-center">
                          <span className="text-gray-500 text-sm">成功率</span>
                          <span className="font-mono font-bold text-green-600 text-lg">
                            {maintenanceStats.dream.total_cycles > 0
                              ? `${((maintenanceStats.dream.successful_cycles || 0) / maintenanceStats.dream.total_cycles * 100).toFixed(1)}%`
                              : '0%'}
                          </span>
                        </div>
                        <div className="flex justify-between items-center">
                          <span className="text-gray-500 text-sm">运行状态</span>
                          <span className={`px-2 py-1 rounded text-xs font-bold ${maintenanceStats.dream.is_running ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                            {maintenanceStats.dream.is_running ? 'RUNNING' : 'STOPPED'}
                          </span>
                        </div>
                      </div>
                    ) : (
                      <div className="text-center py-8 text-gray-400 text-sm">暂无数据</div>
                    )}
                  </div>

                  {/* Check System */}
                  <div className="bg-white border border-gray-200 rounded-xl p-6 hover:shadow-md transition-all">
                    <div className="flex items-center gap-3 mb-5 pb-4 border-b border-gray-100">
                      <div className="p-2 bg-green-50 rounded-lg text-green-600">
                        <Settings className="w-5 h-5" />
                      </div>
                      <h3 className="font-bold text-gray-900 text-lg">表达检查</h3>
                    </div>
                    {maintenanceStats.check ? (
                      <div className="space-y-4">
                        <div className="flex justify-between items-center">
                          <span className="text-gray-500 text-sm">已检查</span>
                          <span className="font-mono font-bold text-gray-900 text-lg">{maintenanceStats.check.total_checked}</span>
                        </div>
                        <div className="flex justify-between items-center">
                          <span className="text-gray-500 text-sm">接受率</span>
                          <span className="font-mono font-bold text-blue-600 text-lg">
                            {maintenanceStats.check.total_checked > 0
                              ? `${((maintenanceStats.check.total_accepted || 0) / maintenanceStats.check.total_checked * 100).toFixed(1)}%`
                              : '0%'}
                          </span>
                        </div>
                        <div className="flex gap-2 mt-2 pt-2 border-t border-gray-50">
                          <div className="flex-1 bg-green-50 text-green-700 text-xs py-1.5 px-3 rounded-lg text-center font-bold">
                            +{maintenanceStats.check.total_accepted} 接受
                          </div>
                          <div className="flex-1 bg-red-50 text-red-700 text-xs py-1.5 px-3 rounded-lg text-center font-bold">
                            -{maintenanceStats.check.total_rejected} 拒绝
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="text-center py-8 text-gray-400 text-sm">暂无数据</div>
                    )}
                  </div>

                  {/* Reflect System */}
                  <div className="bg-white border border-gray-200 rounded-xl p-6 hover:shadow-md transition-all">
                    <div className="flex items-center gap-3 mb-5 pb-4 border-b border-gray-100">
                      <div className="p-2 bg-purple-50 rounded-lg text-purple-600">
                        <Settings className="w-5 h-5" />
                      </div>
                      <h3 className="font-bold text-gray-900 text-lg">表达反思</h3>
                    </div>
                    {maintenanceStats.reflect ? (
                      <div className="space-y-4">
                        <div className="flex justify-between items-center">
                          <span className="text-gray-500 text-sm">反思次数</span>
                          <span className="font-mono font-bold text-gray-900 text-lg">{maintenanceStats.reflect.total_reflections}</span>
                        </div>
                        <div className="flex justify-between items-center">
                          <span className="text-gray-500 text-sm">建议数</span>
                          <span className="font-mono font-bold text-purple-600 text-lg">{maintenanceStats.reflect.total_recommendations}</span>
                        </div>
                        <div className="flex justify-between items-center">
                          <span className="text-gray-500 text-sm">追踪表达</span>
                          <span className="font-mono font-bold text-blue-600 text-lg">{maintenanceStats.reflect.tracked_expressions}</span>
                        </div>
                      </div>
                    ) : (
                      <div className="text-center py-8 text-gray-400 text-sm">暂无数据</div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Knowledge Graph Tab */}
            {activeTab === 8 && (
              <div className="space-y-6">
                {/* Stats Cards */}
                {kgStats && (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {[
                      { label: '知识三元组', value: kgStats.triples, color: 'bg-blue-500' },
                      { label: '实体数量', value: kgStats.entities, color: 'bg-green-500' },
                      { label: '关系类型', value: kgStats.relationships, color: 'bg-purple-500' },
                      { label: '平均置信度', value: `${(kgStats.avg_confidence * 100).toFixed(1)}%`, color: 'bg-orange-500' }
                    ].map((stat, i) => (
                      <div key={i} className={`${stat.color} rounded-xl p-5 text-white shadow-sm hover:shadow-md transition-shadow`}>
                        <div className="text-sm font-medium opacity-90">{stat.label}</div>
                        <div className="text-3xl font-bold mt-2">{stat.value}</div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Sub Tabs */}
                <div className="flex space-x-6 border-b border-gray-200">
                  <button
                    onClick={() => setKgActiveSubTab('triples')}
                    className={`pb-3 text-sm font-bold border-b-2 transition-colors ${
                      kgActiveSubTab === 'triples' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'
                    }`}
                  >
                    知识三元组
                  </button>
                  <button
                    onClick={() => setKgActiveSubTab('query')}
                    className={`pb-3 text-sm font-bold border-b-2 transition-colors ${
                      kgActiveSubTab === 'query' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'
                    }`}
                  >
                    自然语言查询
                  </button>
                </div>

                {kgActiveSubTab === 'triples' && (
                  <div className="space-y-4">
                    {kgTriples.length > 0 ? (
                      <div className="grid gap-4">
                        {kgTriples.slice(0, 10).map((triple: any, idx: number) => (
                          <div key={idx} className="bg-white border border-gray-200 rounded-xl p-5 hover:shadow-md transition-all">
                            <div className="flex flex-wrap items-center gap-3 text-sm mb-3">
                              <span className="font-bold text-gray-900 bg-gray-100 px-3 py-1 rounded-lg border border-gray-200">{triple.subject}</span>
                              <span className="text-gray-400">→</span>
                              <span className="text-blue-600 font-bold bg-blue-50 px-3 py-1 rounded-lg border border-blue-100">{triple.predicate}</span>
                              <span className="text-gray-400">→</span>
                              <span className="font-bold text-gray-900 bg-gray-100 px-3 py-1 rounded-lg border border-gray-200">{triple.object}</span>
                              <span className="ml-auto text-xs font-bold text-green-700 bg-green-50 px-2.5 py-1 rounded-full border border-green-100">
                                {(triple.confidence * 100).toFixed(0)}% Conf
                              </span>
                            </div>
                            {triple.context && (
                              <div className="text-sm text-gray-600 bg-gray-50/50 p-3 rounded-xl border border-gray-100 mb-3 leading-relaxed">
                                {triple.context}
                              </div>
                            )}
                            <div className="text-xs text-gray-400 flex justify-between font-mono pt-2 border-t border-gray-50">
                              <span>SOURCE: {triple.source_chat_id}</span>
                              <span>{new Date(triple.timestamp * 1000).toLocaleString('zh-CN')}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                       <div className="text-center py-12 bg-white rounded-xl border border-dashed border-gray-200 text-gray-400">暂无数据</div>
                    )}
                  </div>
                )}

                {kgActiveSubTab === 'query' && (
                  <div className="space-y-6">
                    <div className="flex gap-3">
                      <input
                        type="text"
                        placeholder="输入自然语言查询... (例如: 小明喜欢什么)"
                        value={kgQueryText}
                        onChange={(e) => setKgQueryText(e.target.value)}
                        onKeyPress={(e) => e.key === 'Enter' && handleKgQuery()}
                        className="flex-1 px-5 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent shadow-sm text-base"
                      />
                      <button
                        onClick={handleKgQuery}
                        disabled={kgQuerying || !kgQueryText.trim()}
                        className="px-8 py-3 bg-blue-600 text-white font-bold rounded-xl hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed shadow-md flex items-center gap-2 transition-all"
                      >
                        {kgQuerying ? <Loader2 className="w-5 h-5 animate-spin" /> : <Search className="w-5 h-5" />}
                        查询
                      </button>
                    </div>

                    {kgQueryResults.length > 0 && (
                      <div className="space-y-4">
                        <p className="text-sm text-gray-500 font-bold px-1">找到 {kgQueryResults.length} 条相关结果</p>
                        {kgQueryResults.map((triple: any, idx: number) => (
                          <div key={idx} className="bg-white border border-gray-200 rounded-xl p-5 hover:shadow-md transition-all">
                            <div className="flex flex-wrap items-center gap-3 text-sm mb-3">
                              <span className="font-bold text-gray-900 bg-gray-100 px-3 py-1 rounded-lg border border-gray-200">{triple.subject}</span>
                              <span className="text-gray-400">→</span>
                              <span className="text-blue-600 font-bold bg-blue-50 px-3 py-1 rounded-lg border border-blue-100">{triple.predicate}</span>
                              <span className="text-gray-400">→</span>
                              <span className="font-bold text-gray-900 bg-gray-100 px-3 py-1 rounded-lg border border-gray-200">{triple.object}</span>
                            </div>
                            <div className="text-sm text-gray-600 bg-gray-50/50 p-3 rounded-xl border border-gray-100 leading-relaxed">
                              {triple.context}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* HeartFlow Tab */}
            {activeTab === 9 && (
              <div className="space-y-6">
                {/* Stats Overview */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {[
                     { label: '活跃对话', value: heartflowChats.length, color: 'bg-purple-500' },
                     { label: '总消息数', value: heartflowChats.reduce((sum, chat) => sum + (chat.message_count || 0), 0), color: 'bg-green-500' },
                     { label: '总回复数', value: heartflowChats.reduce((sum, chat) => sum + (chat.reply_count || 0), 0), color: 'bg-blue-500' },
                     { label: '平均回复率', value: `${heartflowChats.length > 0 ? (heartflowChats.reduce((sum, chat) => sum + (chat.reply_ratio || 0), 0) / heartflowChats.length * 100).toFixed(1) : 0}%`, color: 'bg-orange-500' }
                  ].map((stat, i) => (
                    <div key={i} className={`${stat.color} rounded-xl p-5 text-white shadow-sm hover:shadow-md transition-all`}>
                      <div className="text-sm font-medium opacity-90">{stat.label}</div>
                      <div className="text-3xl font-bold mt-2">{stat.value}</div>
                    </div>
                  ))}
                </div>

                <div className="space-y-4">
                   {heartflowChats.length === 0 ? (
                      <div className="py-16 text-center text-gray-400 bg-white rounded-xl border border-dashed border-gray-200">暂无活跃对话</div>
                   ) : (
                      <div className="grid gap-4">
                        {heartflowChats.map((chat: any) => (
                          <div 
                             key={chat.chat_id}
                             onClick={() => loadHeartflowChatDetails(chat.chat_id)}
                             className="bg-white border border-gray-200 rounded-xl p-5 hover:shadow-md cursor-pointer transition-all hover:border-blue-300 group"
                          >
                             <div className="flex justify-between items-start mb-4">
                                <h3 className="font-mono font-bold text-gray-900 text-lg group-hover:text-blue-600 transition-colors">{chat.chat_id}</h3>
                                <div className="flex gap-2">
                                   <span className="px-3 py-1 bg-gray-100 text-gray-700 rounded-lg text-xs font-bold uppercase tracking-wide border border-gray-200">
                                      {chat.atmosphere}
                                   </span>
                                   <span className="px-3 py-1 bg-blue-50 text-blue-700 rounded-lg text-xs font-bold uppercase tracking-wide border border-blue-100">
                                      {chat.emotional_state}
                                   </span>
                                </div>
                             </div>
                             <div className="grid grid-cols-4 gap-4 text-sm bg-gray-50/50 p-4 rounded-xl border border-gray-100">
                                <div>
                                   <span className="text-gray-500 block text-xs font-medium mb-1">参与者</span>
                                   <span className="font-bold text-gray-900">{chat.active_participants || 0}</span>
                                </div>
                                <div>
                                   <span className="text-gray-500 block text-xs font-medium mb-1">消息</span>
                                   <span className="font-bold text-gray-900">{chat.message_count || 0}</span>
                                </div>
                                <div>
                                   <span className="text-gray-500 block text-xs font-medium mb-1">回复率</span>
                                   <span className="font-bold text-gray-900">{((chat.reply_ratio || 0) * 100).toFixed(0)}%</span>
                                </div>
                                <div>
                                   <span className="text-gray-500 block text-xs font-medium mb-1">热度</span>
                                   <span className="font-bold text-gray-900">{((chat.topic_activity || 0) * 100).toFixed(0)}%</span>
                                </div>
                             </div>
                          </div>
                        ))}
                      </div>
                   )}
                </div>
                
                {selectedHeartflowChat && (
                  <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4 backdrop-blur-sm">
                     <div className="bg-white rounded-2xl shadow-2xl max-w-lg w-full p-6">
                        <div className="flex justify-between items-center mb-6 border-b border-gray-100 pb-4">
                           <h3 className="text-xl font-bold text-gray-900">对话详情</h3>
                           <button onClick={() => setSelectedHeartflowChat(null)} className="text-gray-400 hover:text-gray-600 p-1 hover:bg-gray-100 rounded-full transition-colors">
                             <Trash2 className="w-5 h-5 rotate-45" /> {/* Using Trash2 as close icon placeholder, should ideally be X */}
                           </button>
                        </div>
                        {/* ... Detail content ... */}
                     </div>
                  </div>
                )}
              </div>
            )}

            {/* Config Tab */}
            {activeTab === 10 && learningConfig && (
              <div className="space-y-6 max-w-4xl">
                <div className="grid gap-6 md:grid-cols-2">
                  {[
                    { key: 'expression_learning', title: '表达方式学习', sub: [
                        { k: 'use_expressions', l: '在回复中使用学到的表达' },
                        { k: 'auto_check', l: '自动检查表达质量' }
                      ]
                    },
                    { key: 'jargon_learning', title: '黑话术语学习', sub: [
                        { k: 'explain_jargons', l: '在回复中解释黑话' }
                      ]
                    },
                    { key: 'sticker_learning', title: '表情包学习', sub: [
                        { k: 'use_stickers', l: '在回复中使用表情包' }
                      ]
                    },
                    { key: 'knowledge_graph', title: '知识图谱', sub: [
                        { k: 'extract_triples', l: '自动提取知识三元组' }
                      ]
                    },
                    { key: 'heartflow', title: 'HeartFlow 对话流', sub: [
                        { k: 'track_emotions', l: '追踪情感状态' },
                        { k: 'track_atmosphere', l: '追踪对话氛围' }
                      ]
                    }
                  ].map(section => (
                    <div key={section.key} className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm hover:shadow-md transition-all">
                      <div className="flex items-center justify-between mb-5">
                        <h3 className="font-bold text-gray-900 text-lg">{section.title}</h3>
                        <label className="relative inline-flex items-center cursor-pointer">
                          <input
                            type="checkbox"
                            checked={learningConfig[section.key]?.enabled ?? true}
                            onChange={(e) => setLearningConfig({
                              ...learningConfig,
                              [section.key]: { ...learningConfig[section.key], enabled: e.target.checked }
                            })}
                            className="sr-only peer"
                          />
                          <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                        </label>
                      </div>
                      
                      <div className={`space-y-3 transition-opacity ${!learningConfig[section.key]?.enabled ? 'opacity-50' : ''}`}>
                        {section.sub.map(subItem => (
                          <div key={subItem.k} className="flex items-center gap-3 p-3 rounded-lg hover:bg-gray-50 transition-colors border border-transparent hover:border-gray-100">
                            <input
                              type="checkbox"
                              checked={learningConfig[section.key]?.[subItem.k] ?? true}
                              onChange={(e) => setLearningConfig({
                                ...learningConfig,
                                [section.key]: { ...learningConfig[section.key], [subItem.k]: e.target.checked }
                              })}
                              disabled={!learningConfig[section.key]?.enabled}
                              className="w-4 h-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
                            />
                            <span className="text-sm font-medium text-gray-700">{subItem.l}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>

                <div className="sticky bottom-4 flex justify-end">
                  <button
                    onClick={saveLearningConfig}
                    disabled={savingConfig}
                    className="px-8 py-3 bg-blue-600 text-white font-bold rounded-xl hover:bg-blue-700 disabled:opacity-50 shadow-lg hover:shadow-xl transition-all"
                  >
                    {savingConfig ? '保存中...' : '保存所有配置'}
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default AILearningPage;
