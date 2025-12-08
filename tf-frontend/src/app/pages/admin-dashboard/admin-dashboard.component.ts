import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { HeaderComponent } from '../../components/header/header.component';
import { AuthService } from '../../services/auth.service';

interface DashboardStats {
  totalUsers: number;
  totalCandidates: number;
  totalCompanies: number;
  pendingCompanies: number;
}

interface Company {
  id: number;
  email: string;
  nombre: string;
  descripcion?: string;
  verified: boolean;
  created_at?: string;
}

interface Candidate {
  id: number;
  email: string;
  nombre: string;
  apellido: string;
  created_at?: string;
  cv_filename?: string;
}

@Component({
  selector: 'app-admin-dashboard',
  standalone: true,
  imports: [CommonModule, HeaderComponent],
  templateUrl: './admin-dashboard.component.html',
  styleUrls: ['./admin-dashboard.component.css']
})
export class AdminDashboardComponent implements OnInit {
  // Estados de carga
  loadingStats = true;
  loadingCompanies = true;
  loadingCandidates = true;

  // Datos
  stats: DashboardStats = {
    totalUsers: 0,
    totalCandidates: 0,
    totalCompanies: 0,
    pendingCompanies: 0
  };

  pendingCompanies: Company[] = [];
  allCompanies: Company[] = [];
  recentCandidates: Candidate[] = [];

  // Vista activa
  activeView: 'dashboard' | 'companies' | 'candidates' = 'dashboard';

  // Filtros
  companyFilter: 'all' | 'verified' | 'pending' = 'all';

  constructor(
    private authService: AuthService,
    private router: Router
  ) {}

  ngOnInit(): void {
    this.loadDashboardData();
  }

  loadDashboardData(): void {
    this.loadStats();
    this.loadPendingCompanies();
    this.loadAllCompanies();
    this.loadRecentCandidates();
  }

  loadStats(): void {
    this.loadingStats = true;
    console.log('🔄 Iniciando carga de estadísticas...');

    // Calcular estadísticas de usuarios
    this.calculateStatsManually();
  }

  calculateStatsManually(): void {
    console.log('📊 Calculando estadísticas manualmente...');

    // Obtener todos los usuarios
    this.authService.getAllUsers(0, 1000).subscribe({
      next: (users: any[]) => {
        console.log('👥 Usuarios obtenidos:', users.length);

        const candidates = users.filter(u => u.role === 'candidato');
        const companies = users.filter(u => u.role === 'empresa');
        const pendingCompanies = companies.filter(c => !c.verified);

        console.log('📈 Candidatos:', candidates.length);
        console.log('🏢 Empresas:', companies.length);
        console.log('⏳ Empresas pendientes:', pendingCompanies.length);

        this.stats.totalUsers = users.length;
        this.stats.totalCandidates = candidates.length;
        this.stats.totalCompanies = companies.length;
        this.stats.pendingCompanies = pendingCompanies.length;

        console.log('✅ Estadísticas finales:', this.stats);
        this.loadingStats = false;
      },
      error: (error: any) => {
        console.error('❌ Error obteniendo usuarios:', error);
        this.loadingStats = false;
      }
    });
  }

  loadPendingCompanies(): void {
    this.authService.getAllUsers(0, 1000).subscribe({
      next: (users: any[]) => {
        this.pendingCompanies = users
          .filter(u => u.role === 'empresa' && !u.verified)
          .map(u => ({
            id: u.id,
            email: u.email,
            nombre: u.nombre || 'Sin nombre',
            descripcion: u.descripcion,
            verified: u.verified,
            created_at: u.created_at
          }));
      },
      error: (error: any) => {
        console.error('Error cargando empresas pendientes:', error);
      }
    });
  }

  loadAllCompanies(): void {
    this.loadingCompanies = true;
    this.authService.getAllUsers(0, 1000).subscribe({
      next: (users: any[]) => {
        this.allCompanies = users
          .filter(u => u.role === 'empresa')
          .map(u => ({
            id: u.id,
            email: u.email,
            nombre: u.nombre || 'Sin nombre',
            descripcion: u.descripcion,
            verified: u.verified,
            created_at: u.created_at
          }));
        this.loadingCompanies = false;
      },
      error: (error: any) => {
        console.error('Error cargando empresas:', error);
        this.loadingCompanies = false;
      }
    });
  }

  loadRecentCandidates(): void {
    this.loadingCandidates = true;
    this.authService.getAllUsers(0, 1000).subscribe({
      next: (users: any[]) => {
        this.recentCandidates = users
          .filter(u => u.role === 'candidato')
          .slice(0, 10)
          .map(u => ({
            id: u.id,
            email: u.email,
            nombre: u.nombre || '',
            apellido: u.apellido || '',
            created_at: u.created_at,
            cv_filename: u.cv_filename
          }));
        this.loadingCandidates = false;
      },
      error: (error: any) => {
        console.error('Error cargando candidatos:', error);
        this.loadingCandidates = false;
      }
    });
  }

  // Gestión de empresas
  verifyCompany(companyEmail: string): void {
    if (confirm('¿Verificar esta empresa?')) {
      this.authService.verifyCompany(companyEmail).subscribe({
        next: () => {
          alert('Empresa verificada exitosamente');
          this.loadDashboardData();
        },
        error: (error: any) => {
          console.error('Error verificando empresa:', error);
          alert('Error al verificar la empresa');
        }
      });
    }
  }

  // Navegación
  setActiveView(view: 'dashboard' | 'companies' | 'candidates'): void {
    this.activeView = view;
  }

  // Filtros
  get filteredCompanies(): Company[] {
    if (this.companyFilter === 'all') {
      return this.allCompanies;
    } else if (this.companyFilter === 'verified') {
      return this.allCompanies.filter(c => c.verified);
    } else {
      return this.allCompanies.filter(c => !c.verified);
    }
  }

  logout(): void {
    this.authService.logout();
    this.router.navigate(['/login']);
  }
}
