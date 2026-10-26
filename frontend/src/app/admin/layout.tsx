"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { 
  LayoutDashboard, 
  FileText, 
  PlusCircle, 
  LogOut, 
  ExternalLink, 
  ShieldCheck, 
  User, 
  Menu, 
  X,
  ChevronRight,
  Sparkles
} from "lucide-react";
import { 
  isAdminLoggedIn, 
  getStoredAdminUser, 
  adminLogout 
} from "@/services/adminService";
import { AdminUser } from "@/types/admin";

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const [adminUser, setAdminUser] = useState<AdminUser | null>(null);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [isReady, setIsReady] = useState(false);

  const isLoginPage = pathname === "/admin/login";

  useEffect(() => {
    if (isLoginPage) {
      setIsReady(true);
      return;
    }

    if (!isAdminLoggedIn()) {
      router.push("/admin/login");
      return;
    }

    setAdminUser(getStoredAdminUser());
    setIsReady(true);
  }, [pathname, isLoginPage, router]);

  // Don't render sidebar or header on the login page
  if (isLoginPage) {
    return <>{children}</>;
  }

  if (!isReady) {
    return (
      <div className="min-h-screen bg-brand-bg flex items-center justify-center">
        <div className="text-center space-y-2">
          <div className="w-8 h-8 border-3 border-brand-blue border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-xs font-bold text-slate-500">Loading admin panel...</p>
        </div>
      </div>
    );
  }

  const normalizedPath = pathname.replace(/\/+$/, "");

  const navItems = [
    {
      name: "Dashboard",
      href: "/admin/dashboard",
      icon: LayoutDashboard,
      active: normalizedPath === "/admin/dashboard",
    },
    {
      name: "AI Scheme Discovery",
      href: "/admin/discovery",
      icon: Sparkles,
      active: normalizedPath === "/admin/discovery",
    },
    {
      name: "Manage Schemes",
      href: "/admin/schemes",
      icon: FileText,
      active: normalizedPath === "/admin/schemes" || (normalizedPath.startsWith("/admin/schemes/") && normalizedPath !== "/admin/schemes/new"),
    },
    {
      name: "Add New Scheme",
      href: "/admin/schemes/new",
      icon: PlusCircle,
      active: normalizedPath === "/admin/schemes/new",
    },
  ];

  return (
    <div className="min-h-screen bg-brand-bg flex flex-col md:flex-row">
      {/* Mobile Top Header */}
      <div className="md:hidden bg-white border-b border-brand-border px-4 py-3 flex items-center justify-between sticky top-0 z-30">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-blue-50 border border-blue-200 flex items-center justify-center">
            <ShieldCheck className="w-5 h-5 text-brand-blue" />
          </div>
          <span className="font-extrabold text-brand-navy text-sm">
            Admin<span className="text-brand-blue"> Portal</span>
          </span>
        </div>
        <button
          onClick={() => setMobileSidebarOpen(!mobileSidebarOpen)}
          className="p-2 rounded-lg text-slate-600 hover:bg-slate-100"
          aria-label="Toggle Menu"
        >
          {mobileSidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {/* Mobile Backdrop */}
      {mobileSidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-30 md:hidden backdrop-blur-xs transition-opacity"
          onClick={() => setMobileSidebarOpen(false)}
        />
      )}

      {/* Sidebar Navigation */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-64 bg-brand-navy-dark text-white flex flex-col justify-between transition-transform duration-200 ease-in-out md:translate-x-0 overflow-y-auto ${
          mobileSidebarOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
        }`}
      >
        <div className="p-6 space-y-6">
          {/* Logo / Title */}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-blue-500/20 border border-blue-400/30 flex items-center justify-center shadow-xs">
              <ShieldCheck className="w-6 h-6 text-brand-teal" />
            </div>
            <div>
              <div className="font-black text-base tracking-tight text-white">
                Yojana Hunter
              </div>
              <div className="text-[11px] font-bold text-brand-teal uppercase tracking-wider">
                Admin Console
              </div>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="space-y-1.5 pt-4 border-t border-white/10">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <Link
                  key={item.name}
                  href={item.href}
                  onClick={() => setMobileSidebarOpen(false)}
                  className={`flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs sm:text-sm font-bold transition group ${
                    item.active
                      ? "bg-brand-blue text-white shadow-sm"
                      : "text-slate-300 hover:bg-white/10 hover:text-white"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <Icon className="w-4 h-4 text-slate-400 group-hover:text-white" />
                    <span>{item.name}</span>
                  </div>
                  {item.active && <ChevronRight className="w-4 h-4 text-white/70" />}
                </Link>
              );
            })}
          </nav>

          {/* Public Portal Link */}
          <div className="pt-4 border-t border-white/10">
            <Link
              href="/schemes"
              target="_blank"
              className="flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-semibold text-slate-300 hover:bg-white/10 hover:text-white transition"
            >
              <div className="flex items-center gap-2.5">
                <ExternalLink className="w-4 h-4 text-brand-teal" />
                <span>View Citizen Portal</span>
              </div>
            </Link>
          </div>
        </div>

        {/* Profile & Logout Section at bottom of sidebar */}
        <div className="p-4 m-4 rounded-xl bg-white/5 border border-white/10 space-y-3">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-brand-blue flex items-center justify-center text-white text-xs font-bold">
              {adminUser?.email ? adminUser.email[0].toUpperCase() : "A"}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-bold text-white truncate">
                {adminUser?.email || "Admin Officer"}
              </p>
              <p className="text-[10px] text-emerald-400 font-medium capitalize">
                {adminUser?.role || "Administrator"}
              </p>
            </div>
          </div>

          <button
            onClick={() => adminLogout()}
            className="w-full flex items-center justify-center gap-2 py-2 px-3 bg-white/10 hover:bg-rose-500/20 hover:text-rose-300 text-slate-300 text-xs font-bold rounded-lg transition"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span>Sign Out</span>
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 md:pl-64">
        {/* Top Header Bar on desktop */}
        <header className="hidden md:flex h-16 bg-white border-b border-brand-border px-8 items-center justify-between sticky top-0 z-20">
          <div className="flex items-center gap-3">
            <h2 className="text-sm font-extrabold text-brand-navy">
              Government Scheme Administration System
            </h2>
            <span className="px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 text-[10px] font-bold border border-emerald-200">
              PostgreSQL 18 Connected
            </span>
          </div>

          <div className="flex items-center gap-4">
            <div className="text-right">
              <span className="block text-xs font-bold text-brand-navy">
                {adminUser?.email || "admin@yojanahunter.gov.in"}
              </span>
              <span className="block text-[10px] text-slate-500 font-medium">
                Role: Administrator
              </span>
            </div>
            <button
              onClick={() => adminLogout()}
              className="p-2 rounded-xl text-slate-500 hover:text-rose-600 hover:bg-rose-50 transition"
              title="Sign Out"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </header>

        {/* Child Page Content */}
        <main className="flex-1 p-4 sm:p-6 lg:p-8">
          {children}
        </main>
      </div>
    </div>
  );
}
