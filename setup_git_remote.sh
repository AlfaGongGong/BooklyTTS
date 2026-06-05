#!/data/data/com.termux/files/usr/bin/bash
# setup_git_remote.sh - Konfiguriše git remote za BooklyTTS
# Verzija 2.1 - main branch only

set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC}  $*"; }
warn() { echo -e "${YELLOW}[--]${NC}  $*"; }
err()  { echo -e "${RED}[ERR]${NC} $*"; }

GITHUB_USERNAME="AlfaGongGong"
REPO_NAME="BooklyTTS"
MAIN_BRANCH="main"

echo -e "${BLUE}════════════════════════════════════════${NC}"
echo -e "${BLUE}   GIT REMOTE SETUP ZA BOOKLYTTS${NC}"
echo -e "${BLUE}════════════════════════════════════════${NC}"
echo "📍 Trenutni direktorij: $(pwd)"
echo ""

# Provjeri da li smo u git repo
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo -e "${RED}❌ Niste u git repozitoriju!${NC}"
    echo "Pokrenite prvo: git init"
    exit 1
fi

# ═══════════════════════════════════════════════════════════
# OSIGURAJ DA KORISTIMO 'main' GRANU
# ═══════════════════════════════════════════════════════════
current_branch=$(git branch --show-current)

if [[ "$current_branch" != "$MAIN_BRANCH" ]]; then
    echo -e "${YELLOW}⚠️  Trenutna grana: $current_branch${NC}"
    echo -e "${BLUE}   Potrebno je koristiti '$MAIN_BRANCH' granu.${NC}"
    echo ""
    
    # Provjeri da li 'main' grana već postoji
    if git show-ref --verify --quiet "refs/heads/$MAIN_BRANCH"; then
        echo -e "${GREEN}✅ '$MAIN_BRANCH' grana postoji${NC}"
        read -p "Prebaciti se na '$MAIN_BRANCH'? (D/n): " prebaci
        if [[ ! "$prebaci" =~ ^[Nn] ]]; then
            git checkout "$MAIN_BRANCH"
            ok "Prebačeno na '$MAIN_BRANCH'"
        fi
    else
        echo -e "${YELLOW}📝 '$MAIN_BRANCH' grana ne postoji${NC}"
        echo ""
        echo "Opcije:"
        echo "1. Preimenuj '$current_branch' → '$MAIN_BRANCH' (preporučeno)"
        echo "2. Kreiraj novu '$MAIN_BRANCH' i prebaci se"
        echo "3. Ostani na '$current_branch'"
        echo ""
        read -p "Izbor (1-3) [1]: " grana_izbor
        grana_izbor=${grana_izbor:-1}
        
        case $grana_izbor in
            1)
                echo "🔄 Preimenujem '$current_branch' → '$MAIN_BRANCH'..."
                git branch -m "$current_branch" "$MAIN_BRANCH"
                ok "Grana preimenovana u '$MAIN_BRANCH'"
                ;;
            2)
                echo "📝 Kreiram novu '$MAIN_BRANCH'..."
                git checkout -b "$MAIN_BRANCH"
                ok "Nova grana '$MAIN_BRANCH' kreirana"
                ;;
            3)
                warn "Ostajete na '$current_branch'. Push će ići na ovu granu."
                MAIN_BRANCH="$current_branch"
                ;;
            *)
                err "Pogrešan izbor!"
                exit 1
                ;;
        esac
    fi
fi

echo ""

# Provjeri postojanje remote-a
if git remote -v 2>/dev/null | grep -q "origin"; then
    echo -e "${YELLOW}✅ Remote 'origin' već postoji:${NC}"
    git remote -v
    echo ""
    read -p "Želite li ga promijeniti? (d/N): " promijeni
    if [[ ! "$promijeni" =~ ^[Dd] ]]; then
        echo "Zadržavam postojeći remote."
        exit 0
    fi
    git remote remove origin
fi

echo "Odaberite tip remote-a:"
echo "1. GitHub (HTTPS) - Preporučeno za Termux"
echo "2. GitHub (SSH) - Potreban SSH ključ"
echo "3. Lokalni backup (SD kartica)"
echo "4. Ručno unesite URL"
echo ""
read -p "Izbor (1-4) [1]: " izbor
izbor=${izbor:-1}

case $izbor in
    1)
        remote_url="https://github.com/${GITHUB_USERNAME}/${REPO_NAME}.git"
        echo -e "\n${BLUE}🌐 GitHub HTTPS:${NC} $remote_url"
        
        # Provjeri da li repo postoji na GitHub-u
        echo "🔍 Provjeravam da li repozitorij postoji..."
        if curl -s -o /dev/null -w "%{http_code}" "https://github.com/${GITHUB_USERNAME}/${REPO_NAME}" | grep -q "200"; then
            ok "Repozitorij postoji na GitHub-u"
        else
            warn "Repozitorij ne postoji na GitHub-u"
            echo ""
            echo -e "${YELLOW}📝 Potrebno je kreirati repozitorij na GitHub-u.${NC}"
            echo "   Idite na: https://github.com/new"
            echo "   Naziv: ${REPO_NAME}"
            echo "   ⚠️  NE dodavajte README, .gitignore ili licencu!"
            echo ""
            read -p "Jeste li kreirali repo? (d/N): " kreiran
            
            if [[ ! "$kreiran" =~ ^[Dd] ]]; then
                echo ""
                echo -e "${YELLOW}💡 Opcije:${NC}"
                echo "   1. Otvorite link u browseru i kreirajte repo"
                echo "   2. Koristite GitHub CLI (gh) ako je instaliran"
                echo "   3. Odaberite lokalni backup (opcija 3)"
                echo ""
                
                # Provjeri da li je GitHub CLI instaliran
                if command -v gh &> /dev/null; then
                    read -p "Želite li kreirati repo koristeći GitHub CLI? (D/n): " koristi_cli
                    if [[ ! "$koristi_cli" =~ ^[Nn] ]]; then
                        echo "🔐 Prijava na GitHub..."
                        gh auth login
                        echo "📦 Kreiram repozitorij..."
                        gh repo create "${REPO_NAME}" --public --source=. --remote=origin --push
                        ok "Repo kreiran i kod pushan!"
                        exit 0
                    fi
                fi
                
                echo -e "\n${YELLOW}Nakon kreiranja repo-a, pokrenite:${NC}"
                echo "  git remote add origin $remote_url"
                echo "  git push -u origin $MAIN_BRANCH"
                exit 0
            fi
            
            # Ponovo provjeri nakon kreiranja
            if curl -s -o /dev/null -w "%{http_code}" "https://github.com/${GITHUB_USERNAME}/${REPO_NAME}" | grep -q "200"; then
                ok "Repo sada postoji!"
            else
                err "Repo još uvijek ne postoji. Provjerite URL."
                exit 1
            fi
        fi
        ;;
        
    2)
        remote_url="git@github.com:${GITHUB_USERNAME}/${REPO_NAME}.git"
        echo -e "\n${BLUE}🔑 GitHub SSH:${NC} $remote_url"
        
        # Provjeri SSH ključ
        if ! ssh -T git@github.com 2>&1 | grep -q "successfully authenticated"; then
            warn "SSH autentikacija nije konfigurisana"
            echo "  Potrebno je dodati SSH ključ na GitHub:"
            echo "  https://github.com/settings/keys"
            
            if [ -f ~/.ssh/id_rsa.pub ]; then
                echo ""
                echo -e "${GREEN}📋 Vaš javni ključ:${NC}"
                cat ~/.ssh/id_rsa.pub
                echo ""
                echo "  Kopirajte ga na: https://github.com/settings/keys"
            fi
            
            read -p "Nastaviti svejedno? (d/N): " nastavi
            if [[ ! "$nastavi" =~ ^[Dd] ]]; then
                exit 1
            fi
        fi
        ;;
        
    3)
        backup_dir="/storage/emulated/0/termux/git-backups"
        echo -e "\n${BLUE}💾 Lokalni backup:${NC} $backup_dir"
        
        mkdir -p "$backup_dir"
        cd "$backup_dir"
        if [ ! -d "${REPO_NAME}.git" ]; then
            echo "📦 Kreiram bare repozitorij..."
            git init --bare "${REPO_NAME}.git"
            ok "Bare repo kreiran"
        else
            ok "Backup repo već postoji"
        fi
        
        cd "$HOME/${REPO_NAME}" 2>/dev/null || cd "$(dirname "$(git rev-parse --git-dir)")"
        remote_url="${backup_dir}/${REPO_NAME}.git"
        echo "   Lokacija: $remote_url"
        ;;
        
    4)
        echo -e "\n${BLUE}🔗 Ručni unos:${NC}"
        read -p "Unesite URL: " remote_url
        ;;
        
    *)
        echo -e "${RED}❌ Pogrešan izbor!${NC}"
        exit 1
        ;;
esac

# Dodaj remote
echo ""
echo "📡 Dodajem remote 'origin'..."
if git remote add origin "$remote_url" 2>/dev/null; then
    ok "Remote dodan"
else
    err "Greška pri dodavanju remote-a"
    exit 1
fi

# Prikaži remote
echo ""
echo -e "${GREEN}✅ Remote konfigurisan:${NC}"
git remote -v
echo ""
echo -e "${BLUE}🌿 Grana:${NC} $MAIN_BRANCH"

# Push
echo ""
read -p "Želite li odmah push na '$MAIN_BRANCH'? (D/n): " push_now
if [[ ! "$push_now" =~ ^[Nn] ]]; then
    echo ""
    echo -e "📤 Push na ${BLUE}$MAIN_BRANCH${NC}..."
    
    if git push -u origin "$MAIN_BRANCH" 2>&1; then
        ok "Push uspješan!"
        echo ""
        echo -e "${GREEN}════════════════════════════════════════${NC}"
        echo -e "${GREEN}   ✅ SVE GOTOVO!${NC}"
        echo -e "${GREEN}════════════════════════════════════════${NC}"
        echo ""
        echo -e "${BLUE}📊 Repozitorij:${NC}"
        echo "   • Lokalni: $(pwd)"
        echo "   • Remote: $remote_url"
        echo "   • Branch: $MAIN_BRANCH"
        echo ""
        
        if [[ $izbor -eq 1 || $izbor -eq 2 ]]; then
            echo -e "${BLUE}🔗 GitHub URL:${NC}"
            echo "   https://github.com/${GITHUB_USERNAME}/${REPO_NAME}"
        fi
    else
        err "Push nije uspio!"
        echo ""
        echo -e "${YELLOW}💡 Mogući problemi:${NC}"
        echo "   • Remote repo nije prazan (ima README.md)"
        echo "   • Nemate permisije za push"
        echo "   • Autentikacija nije uspjela"
        echo ""
        echo -e "${YELLOW}🔧 Rješenja:${NC}"
        echo "   1. git pull origin $MAIN_BRANCH --allow-unrelated-histories"
        echo "   2. git push --force origin $MAIN_BRANCH"
        echo ""
        read -p "Želite li pokušati force push? (n/D): " force
        
        if [[ "$force" =~ ^[Dd] ]]; then
            echo "⚠️  Force push na '$MAIN_BRANCH'..."
            git push --force -u origin "$MAIN_BRANCH"
            ok "Force push uspješan!"
        fi
    fi
else
    echo ""
    echo -e "${YELLOW}💡 Da pushate kasnije, pokrenite:${NC}"
    echo "   git push -u origin $MAIN_BRANCH"
fi

echo ""
echo -e "${GREEN}✅ Git remote konfiguracija završena!${NC}"
