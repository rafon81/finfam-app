# --- generate_keys.py (Versión Definitiva con bcrypt) ---
# Este script ya NO usa streamlit-authenticator para generar las claves.
# Utiliza directamente la librería 'bcrypt', eliminando todos los problemas de versión.
# No necesitas instalar nada nuevo, bcrypt ya viene con streamlit-authenticator.

import bcrypt

print("Generando hashes de contraseñas con el método directo (bcrypt)...")

# Reemplaza con las contraseñas que desees para cada usuario
passwords_to_hash = ["Lore0804", "Rosario1103"]
hashed_passwords = []

for password in passwords_to_hash:
    # Codificar la contraseña a bytes, que es lo que bcrypt necesita
    password_bytes = password.encode('utf-8')
    
    # Generar un "salt" (una cadena aleatoria para hacer el hash más seguro)
    salt = bcrypt.gensalt()
    
    # Crear el hash
    hashed_password_bytes = bcrypt.hashpw(password_bytes, salt)
    
    # Decodificar el hash de vuelta a string para poder guardarlo y mostrarlo
    hashed_passwords.append(hashed_password_bytes.decode('utf-8'))

print("\n✅ ¡Hashes generados con éxito!")
print("Copia y pega las siguientes líneas en tu archivo config.yaml:")
print("---------------------------------------------------------")
print(f"Hash para 'rafa': '{hashed_passwords[0]}'")
print(f"Hash para 'caro': '{hashed_passwords[1]}'")
print("---------------------------------------------------------")
print("\n¡Listo! Ahora tu aplicación principal funcionará sin problemas con estos hashes.")
