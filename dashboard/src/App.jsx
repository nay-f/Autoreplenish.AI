import React, { useState, useEffect } from 'react';
import { AuthProvider } from './context/AuthContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import { Navbar } from './components/Navbar';
import { Sidebar } from './components/Sidebar';
import { ApiStatusBanner } from './components/ApiStatusBanner';
import { InventoryHealth } from './pages/InventoryHealth';
import { ReasoningTrace } from './pages/ReasoningTrace';
import { StoreSettings } from './pages/StoreSettings';
import { SapMonitor } from './pages/SapMonitor';
import { FeedbackAnalytics } from './pages/FeedbackAnalytics';

function DashboardContent() {
  const [activeTab, setActiveTab] = useState('inventory-health');
  const [activeRole, setActiveRole] = useState('Regional Manager');

  // Synchronize tab with window hash if provided
  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash.replace('#', '');
      const validTabs = ['inventory-health', 'reasoning-trace', 'store-settings', 'sap-monitor', 'feedback-analytics'];
      if (validTabs.includes(hash)) {
        setActiveTab(hash);
      }
    };

    handleHashChange();
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  const handleTabChange = (newTab) => {
    setActiveTab(newTab);
    window.location.hash = newTab;
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100">
      <Navbar activeRole={activeRole} setActiveRole={setActiveRole} />

      <div className="flex flex-1">
        <Sidebar activeTab={activeTab} setActiveTab={handleTabChange} />

        <main className="flex-1 p-6 overflow-y-auto max-w-7xl">
          <ApiStatusBanner />
          {activeTab === 'inventory-health' && <InventoryHealth />}
          {activeTab === 'reasoning-trace' && <ReasoningTrace />}
          {activeTab === 'store-settings' && <StoreSettings />}
          {activeTab === 'sap-monitor' && <SapMonitor />}
          {activeTab === 'feedback-analytics' && <FeedbackAnalytics />}
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <ProtectedRoute>
        <DashboardContent />
      </ProtectedRoute>
    </AuthProvider>
  );
}
