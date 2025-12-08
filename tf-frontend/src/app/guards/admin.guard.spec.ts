import { TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { of, Observable } from 'rxjs';
import { adminGuard } from './admin.guard';
import { AuthService } from '../services/auth.service';
import { UserService } from '../services/user.service';

describe('adminGuard', () => {
  let authService: jasmine.SpyObj<AuthService>;
  let userService: jasmine.SpyObj<UserService>;
  let router: jasmine.SpyObj<Router>;

  beforeEach(() => {
    const authServiceSpy = jasmine.createSpyObj('AuthService', ['isAuthenticated']);
    const userServiceSpy = jasmine.createSpyObj('UserService', ['getCurrentUser']);
    const routerSpy = jasmine.createSpyObj('Router', ['navigate']);

    TestBed.configureTestingModule({
      providers: [
        { provide: AuthService, useValue: authServiceSpy },
        { provide: UserService, useValue: userServiceSpy },
        { provide: Router, useValue: routerSpy }
      ]
    });

    authService = TestBed.inject(AuthService) as jasmine.SpyObj<AuthService>;
    userService = TestBed.inject(UserService) as jasmine.SpyObj<UserService>;
    router = TestBed.inject(Router) as jasmine.SpyObj<Router>;
  });

  it('should redirect to login if not authenticated', () => {
    authService.isAuthenticated.and.returnValue(false);

    const result = TestBed.runInInjectionContext(() =>
      adminGuard({} as any, {} as any)
    );

    expect(result).toBe(false);
    expect(router.navigate).toHaveBeenCalledWith(['/login']);
  });

  it('should allow access for admin users', (done) => {
    authService.isAuthenticated.and.returnValue(true);
    userService.getCurrentUser.and.returnValue(of({ role: 'admin' } as any));

    const result = TestBed.runInInjectionContext(() =>
      adminGuard({} as any, {} as any)
    );

    // Check if result is an Observable
    if (result instanceof Observable) {
      result.subscribe(allowed => {
        expect(allowed).toBe(true);
        done();
      });
    } else {
      fail('Expected Observable but got: ' + typeof result);
      done();
    }
  });

  it('should deny access for non-admin users', (done) => {
    authService.isAuthenticated.and.returnValue(true);
    userService.getCurrentUser.and.returnValue(of({ role: 'candidato' } as any));

    spyOn(window, 'alert');

    const result = TestBed.runInInjectionContext(() =>
      adminGuard({} as any, {} as any)
    );

    // Check if result is an Observable
    if (result instanceof Observable) {
      result.subscribe(allowed => {
        expect(allowed).toBe(false);
        expect(router.navigate).toHaveBeenCalledWith(['/inicio']);
        done();
      });
    } else {
      fail('Expected Observable but got: ' + typeof result);
      done();
    }
  });
});
