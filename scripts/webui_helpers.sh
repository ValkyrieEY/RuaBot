#!/bin/bash

# install.sh 与 rcli.sh 共用的 WebUI 构建辅助（需由父脚本提供 log_*、run_long_task、download_with_progress、INSTALL_DIR）

ensure_node_env() {
    if [ -n "$NVM_DIR" ]; then
        [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    elif [ -n "$INSTALL_DIR" ]; then
        export NVM_DIR="$INSTALL_DIR/.nvm"
        [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    fi

    if ! command -v node &> /dev/null; then
        log_error "未找到 Node.js，请先完成 install.sh 中的 Node.js（nvm）安装步骤"
        return 1
    fi

    return 0
}

webui_download_zip() {
    local dest_dir=$1
    local zip_file="$dest_dir/repo.zip"
    local url_main="https://github.com/ValkyrieEY/RuaBot/archive/refs/heads/main.zip"
    local url_master="https://github.com/ValkyrieEY/RuaBot/archive/refs/heads/master.zip"

    log_info "从 GitHub 下载 WebUI 源码压缩包..."
    download_with_progress "$url_main" "$zip_file" "下载 WebUI (main)" || \
    download_with_progress "$url_master" "$zip_file" "下载 WebUI (master)" || return 1

    if [ ! -f "$zip_file" ]; then
        log_error "WebUI 压缩包下载失败或文件不存在"
        return 1
    fi

    if ! unzip -q "$zip_file" -d "$dest_dir" 2>/dev/null; then
        log_error "解压 WebUI 压缩包失败"
        return 1
    fi

    if [ -d "$dest_dir/RuaBot-main/webui" ]; then
        cp -r "$dest_dir/RuaBot-main/webui" "$INSTALL_DIR/"
        return 0
    fi

    if [ -d "$dest_dir/RuaBot-master/webui" ]; then
        cp -r "$dest_dir/RuaBot-master/webui" "$INSTALL_DIR/"
        return 0
    fi

    log_error "压缩包中未找到预期的 webui 目录（RuaBot-main/master）"
    return 1
}

webui_install_or_update() {
    local allow_download=${1:-false}

    cd "$INSTALL_DIR" || return 1

    if ! ensure_node_env; then
        return 1
    fi

    if [ ! -f "$INSTALL_DIR/webui/package.json" ]; then
        if [ "$allow_download" = "true" ]; then
            local temp_dir
            temp_dir=$(mktemp -d)
            if ! webui_download_zip "$temp_dir"; then
                rm -rf "$temp_dir"
                return 1
            fi
            rm -rf "$temp_dir"
        else
            log_warning "未找到 webui/package.json，跳过 WebUI 构建（如需请使用 rcli 安装 WebUI）"
            return 0
        fi
    fi

    if ! run_long_task "WebUI: npm install" bash -lc "cd '$INSTALL_DIR/webui' && npm install"; then
        log_error "WebUI npm install 失败"
        return 1
    fi

    if ! run_long_task "WebUI: npm run build" bash -lc "cd '$INSTALL_DIR/webui' && npm run build"; then
        log_error "WebUI npm run build 失败"
        return 1
    fi

    if [ ! -f "$INSTALL_DIR/src/ui/static/index.html" ]; then
        log_error "构建后未找到前端产物: src/ui/static/index.html"
        return 1
    fi

    log_success "WebUI 已构建并输出到 src/ui/static"
    return 0
}
