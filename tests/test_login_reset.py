import re

from clinic.models import Role, User


ROLE_PASSWORDS = {
    Role.ADMIN: 'Admin123!',
    Role.DOCTOR: 'Dokter123!',
    Role.NURSE: 'Perawat123!',
    Role.PHARMACIST: 'Apoteker123!',
    Role.PATIENT: 'Pasien123!',
    Role.CASHIER: 'Kasir123!',
}


def assert_empty_login_page(response):
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'id="loginForm"' in html
    assert re.search(r'<form[^>]+id="loginForm"[^>]+autocomplete="off"', html)
    assert re.search(r'<input[^>]+id="email"[^>]+value=""[^>]+autocomplete="off"', html)
    assert re.search(r'<input[^>]+id="password"[^>]+value=""[^>]+autocomplete="new-password"', html)
    assert 'autocomplete="username"' not in html
    assert 'autocomplete="current-password"' not in html
    assert response.headers['Cache-Control'] == 'no-store'


def assert_landing_page(response):
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'href="/login"' in html
    assert '>Masuk</a>' in html
    assert 'id="loginForm"' not in html


def test_login_is_empty_for_every_role_and_role_switch(client):
    registration = client.get('/register')
    assert registration.status_code == 200
    assert b'login-split-layout' not in registration.data
    assert b'login-visual-panel' not in registration.data

    roles = list(ROLE_PASSWORDS)
    for role in roles:
        user = User.query.filter_by(role=role).first()
        response = client.post('/login', data={
            'email': user.email,
            'password': ROLE_PASSWORDS[role],
        })
        assert response.status_code == 302

        with client.session_transaction() as session:
            assert session.get('_user_id') == str(user.id)
            session_dump = repr(dict(session))
            assert user.email not in session_dump
            assert ROLE_PASSWORDS[role] not in session_dump

        response = client.post('/logout')
        assert response.status_code == 302
        assert response.headers['Location'].endswith('/')

        with client.session_transaction() as session:
            assert not {'_user_id', '_fresh', '_id'}.intersection(session)

        assert_landing_page(client.get(response.headers['Location']))
        assert_empty_login_page(client.get('/login'))

    for current_role, next_role in zip(roles, roles[1:] + roles[:1]):
        current = User.query.filter_by(role=current_role).first()
        assert client.post('/login', data={
            'email': current.email,
            'password': ROLE_PASSWORDS[current_role],
        }).status_code == 302
        logout_response = client.post('/logout')
        assert logout_response.headers['Location'].endswith('/')
        assert_landing_page(client.get(logout_response.headers['Location']))
        assert_empty_login_page(client.get('/login'))

        following = User.query.filter_by(role=next_role).first()
        assert client.post('/login', data={
            'email': following.email,
            'password': ROLE_PASSWORDS[next_role],
        }).status_code == 302
        client.post('/logout')

    response = client.post('/login', data={
        'email': 'credential-lama@example.test',
        'password': 'PasswordLama123!',
    })
    assert_empty_login_page(response)
    assert b'credential-lama@example.test' not in response.data
    assert b'PasswordLama123!' not in response.data
