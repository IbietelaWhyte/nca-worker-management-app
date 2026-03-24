import Sidebar from './Sidebar'
import TopBar from './TopBar'

export default function AppLayout({ children }) {
  return (
    <div className="flex min-h-screen bg-background">
      {/* Sidebar — fixed on the left */}
      <Sidebar />

      {/* Main area — topbar + page content */}
      <div className="flex flex-col flex-1">
        <TopBar />
        <main className="flex-1 p-6 overflow-auto">
          {children}
        </main>
      </div>
    </div>
  )
}