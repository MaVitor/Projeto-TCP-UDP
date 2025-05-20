### Solução Simples para Conectar em Outro PC

Para conectar o jogo entre computadores diferentes, você só precisa alterar **uma linha** no arquivo `client.py`:

## 1. No computador que vai rodar o servidor:

1. Execute o `server.py` normalmente
2. Descubra o IP deste computador:

1. Abra o Prompt de Comando
2. Digite `ipconfig`
3. Procure por "IPv4" (algo como 192.168.1.X)
4. Anote este número


## 2. No computador que vai rodar o cliente:

1. Abra o arquivo `client.py` em um editor de texto
2. Procure esta linha (deve estar no início do arquivo):

```python
SERVER_HOST = '127.0.0.1'  # Altere para o IP do servidor na rede local
```


3. Substitua por:

```python
SERVER_HOST = '192.168.1.X'  # Substitua pelo IP real do servidor que você anotou
```


4. Salve o arquivo
5. Execute o `client.py`


## Resumo:

1. **Servidor**: Anote o IP (use `ipconfig`)
2. **Cliente**: Mude a linha `SERVER_HOST = '127.0.0.1'` para `SERVER_HOST = 'IP-DO-SERVIDOR'`
3. Execute o cliente