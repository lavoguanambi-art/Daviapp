def clean_emoji_text(text: str) -> str:
    """Limpa emojis e caracteres especiais mantendo a legibilidade"""
    emoji_map = {
        "✏️": "(Editar)",
        "🗑️": "(Excluir)",
        "💰": "(Dinheiro)",
        "✅": "(OK)",
        "❌": "(X)",
        "⚠️": "(Aviso)",
        "🎯": "(Alvo)",
        "🏆": "(Troféu)",
        "⚔️": "(Em Batalha)"
    }
    
    for emoji, replacement in emoji_map.items():
        text = text.replace(emoji, replacement)
    return text

def get_giant_status_text(status: str, meta_atingida: bool = False) -> str:
    """Retorna o texto de status do gigante sem emojis"""
    if status == "defeated":
        return "(Troféu) Derrotado!"
    return "(OK) Meta Atingida" if meta_atingida else "(Em Batalha) Em Andamento"
