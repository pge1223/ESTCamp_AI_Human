/* src/pages/tokenDashboard/tokenDashboard.jsx */
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import '../../index.css';
import './tokenDashboard.css';
import { getDashboard } from '../../lib/tokenDashboardApi';
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
} from 'recharts';

const formatDate = (date) => {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');

    return `${year}-${month}-${day}`;
};

function TokenDashboard() {
    const today = new Date();
    const weekAgo = new Date();
    weekAgo.setDate(today.getDate() - 7);

    const [startDate, setStartDate] = useState(formatDate(weekAgo));
    const [endDate, setEndDate] = useState(formatDate(today));
    const [daily, setDaily] = useState([]);
    const [users, setUsers] = useState([]);

    const navigate = useNavigate();

    const fetchDashboard = async () => {
        const data = await getDashboard(startDate, endDate);
        setDaily(data.daily || []);
        setUsers(data.users || []);
    };

    useEffect(() => {
        fetchDashboard();
    }, []);

    return (
        <div className="app-container">
            <div className="app-wrapper">
                <header className="header">
                    <img src="/assets/logo.png" alt="NodeVelture Logo" className="header-image" />
                    <h1 className="logo" onClick={() => navigate('/')} style={{ cursor: 'pointer' }}>
                        NodeVelture
                    </h1>
                </header>

                <main className="token-dashboard">
                    <h2>토큰 사용량 대시보드</h2>

                    <div className="dashboard-filter">
                        <div className="dashboard-filter-left">
                            <input
                                type="date"
                                value={startDate}
                                onChange={(e) => setStartDate(e.target.value)}
                            />

                            <input
                                type="date"
                                value={endDate}
                                onChange={(e) => setEndDate(e.target.value)}
                            />

                            <button onClick={fetchDashboard}>
                                조회
                            </button>
                        </div>

                        <button
                            onClick={() => navigate("/")}
                        >
                            뒤로가기
                        </button>
                    </div>

                    <section className="dashboard-section">
                        <h3>날짜별 사용량</h3>

                        <div className="chart-container">
                            <ResponsiveContainer width="100%" height={300}>
                                <LineChart data={daily}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis
                                        dataKey="date"
                                        tickMargin={15}
                                    />
                                    <YAxis />
                                    <Tooltip
                                        contentStyle={{
                                            backgroundColor: 'var(--card-main)',
                                            border: `1px solid var(--theme-color)`,
                                            borderRadius: '8px',
                                            color: 'var(--text-main)',
                                        }}
                                        labelStyle={{
                                            color: 'var(--text-main)',
                                        }}
                                        itemStyle={{
                                            color: 'var(--text-main)',
                                        }}
                                        formatter={(value) => [value.toLocaleString(), '총 토큰']}
                                    />
                                    <Line
                                        type="monotone"
                                        dataKey="total_tokens"
                                        name="총 토큰"
                                        strokeWidth={3}
                                        dot
                                    />
                                </LineChart>
                            </ResponsiveContainer>
                        </div>

                        <table>
                            <thead>
                                <tr>
                                    <th>날짜</th>
                                    <th>호출 수</th>
                                    <th>프롬프트 토큰</th>
                                    <th>응답 토큰</th>
                                    <th>총 토큰</th>
                                    <th>비용($)</th>
                                </tr>
                            </thead>
                            <tbody>
                                {daily.map((item) => (
                                    <tr key={item.date}>
                                        <td>{item.date}</td>
                                        <td>{item.total_calls.toLocaleString()}</td>
                                        <td>{item.total_prompt_tokens.toLocaleString()}</td>
                                        <td>{item.total_completion_tokens.toLocaleString()}</td>
                                        <td>{item.total_tokens.toLocaleString()}</td>
                                        <td>{item.total_cost_usd.toLocaleString()}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </section>

                    <section className="dashboard-section">
                        <h3>사용자별 사용량</h3>

                        <table>
                            <thead>
                                <tr>
                                    <th>사용자</th>
                                    <th>이메일</th>
                                    <th>호출 수</th>
                                    <th>총 토큰</th>
                                    <th>비용($)</th>
                                    <th>마지막 사용일</th>
                                </tr>
                            </thead>
                            <tbody>
                                {users.map((user) => (
                                    <tr key={user.user_id || user.username}>
                                        <td>{user.username}</td>
                                        <td>{user.email || '-'}</td>
                                        <td>{user.total_calls.toLocaleString()}</td>
                                        <td>{user.total_tokens.toLocaleString()}</td>
                                        <td>{user.total_cost_usd.toLocaleString()}</td>
                                        <td>{user.last_used_at?.slice(0, 19) || '-'}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </section>
                </main>
            </div>
        </div>
    );
}

export default TokenDashboard;