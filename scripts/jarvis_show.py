"""Ativação por duas palmas para o OpenJarvis.

Uso (na pasta do projeto, ex.: C:\\Users\\mineo\\junior):

    uv run --no-sync python scripts/jarvis_show.py --teste   # só mostra os níveis
    uv run --no-sync python scripts/jarvis_show.py           # escuta e abre o Jarvis

Variáveis de ambiente (no cmd: set NOME=valor):

    JARVIS_CLAP_THRESH  sensibilidade, de 0.0 a 1.0. Menor = mais sensível.
                        Padrão: 0.30
    JARVIS_MIC          número do microfone (veja sd.query_devices()).
                        Padrão: o microfone padrão do Windows.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import time
from pathlib import Path

import numpy as np
import sounddevice as sd

RAIZ = Path(__file__).resolve().parent.parent

BLOCO_SEG = 0.02  # analisa o áudio em blocos de 20 ms
GAP_MIN = 0.12  # intervalo mínimo entre palmas (ignora eco da mesma palma)
GAP_MAX = 0.90  # intervalo máximo entre a primeira e a segunda palma
PAUSA_APOS_ABRIR = 3.0  # espera antes de voltar a escutar


def ler_config() -> tuple[float, int | None]:
    """Lê sensibilidade e microfone das variáveis de ambiente."""
    limiar = float(os.environ.get("JARVIS_CLAP_THRESH", "0.30"))
    mic = os.environ.get("JARVIS_MIC", "").strip()
    return limiar, (int(mic) if mic else None)


class DetectorPalmas:
    """Detecta duas palmas seguidas a partir do pico de volume de cada bloco."""

    def __init__(self, limiar: float) -> None:
        self.limiar = limiar
        self._acima = False
        self._ultima: float | None = None

    def processar(self, pico: float, agora: float) -> bool:
        """Recebe o pico do bloco; devolve True quando acontecem duas palmas."""
        if pico < self.limiar * 0.5:
            self._acima = False  # o som caiu: já pode contar uma nova palma
            return False

        if pico >= self.limiar and not self._acima:
            self._acima = True  # início de uma palma
            if self._ultima is None:
                self._ultima = agora
                return False

            intervalo = agora - self._ultima
            if intervalo < GAP_MIN:
                return False  # eco da mesma palma, ignora
            if intervalo <= GAP_MAX:
                self._ultima = None  # segunda palma: dispara
                return True
            self._ultima = agora  # passou muito tempo: esta vira a primeira
        return False


def escutar(limiar: float, mic: int | None, teste: bool) -> None:
    """Escuta o microfone. No modo normal, retorna quando ouvir duas palmas."""
    info = sd.query_devices(mic, "input")
    taxa = int(info["default_samplerate"])
    bloco = int(taxa * BLOCO_SEG)
    detector = DetectorPalmas(limiar)

    print(f"Microfone: {info['name']} | sensibilidade (limiar): {limiar:.2f}")
    if teste:
        print("Modo teste: bata palmas e veja os níveis. Ctrl+C para sair.")

    # O 'with' fecha o microfone ao sair, liberando-o para o Jarvis usar.
    with sd.InputStream(
        device=mic, channels=1, samplerate=taxa, blocksize=bloco
    ) as fluxo:
        while True:
            dados, _ = fluxo.read(bloco)
            pico = float(np.max(np.abs(dados)))

            if teste and pico >= 0.05:
                print(f"nível {pico:.2f} {'#' * int(pico * 40)}")

            if detector.processar(pico, time.monotonic()):
                if not teste:
                    return
                print(">>> DUAS PALMAS DETECTADAS <<<")


def abrir_jarvis() -> None:
    """Abre o chat de voz numa janela própria e espera ele ser fechado."""
    comando = ["uv", "run", "--no-sync", "jarvis", "chat", "--voice"]
    flags = subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0
    subprocess.run(comando, cwd=RAIZ, creationflags=flags, check=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Duas palmas abrem o Jarvis.")
    parser.add_argument(
        "--teste",
        action="store_true",
        help="só mostra os níveis do microfone, sem abrir o Jarvis",
    )
    args = parser.parse_args()
    limiar, mic = ler_config()

    try:
        if args.teste:
            escutar(limiar, mic, teste=True)
            return
        while True:
            escutar(limiar, mic, teste=False)
            print("Duas palmas! Abrindo o Jarvis...")
            abrir_jarvis()
            print("Jarvis fechado. Voltando a escutar...")
            time.sleep(PAUSA_APOS_ABRIR)
    except KeyboardInterrupt:
        print("\nEncerrado.")


if __name__ == "__main__":
    main()
