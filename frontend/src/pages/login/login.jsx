import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { AuthView } from '@neondatabase/neon-js/auth/react';
import '../../index.css';
import './login.css';

function Login() {
    const navigate = useNavigate();
    const location = useLocation();

    return (
        <div className="app-container">
            <div className="app-wrapper">
                <div className="login-layout">

                    <div className="login-left">
                        <div className="login-wrapper">
                            <header className="header">
                                <img src="/assets/logo.png" alt="NodeVelture Logo" className="header-image" />
                                <h1 className="logo">NodeVelture</h1>
                            </header>

                            <AuthView pathname={location.pathname} />

                            <button className="main-btn" onClick={() => navigate('/')}>
                                main
                            </button>
                        </div>
                    </div>

                    <div className="login-right">
                        <img
                            src="/assets/login.png"
                            alt="NodeVelture Authors"
                            className="login-visual"
                        />
                    </div>
                </div>
            </div>
        </div>
    );
}

export default Login;